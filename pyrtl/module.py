from abc import ABC, abstractmethod
from typing import Tuple, Set
import time
from .core import working_block, Block, _NameIndexer
from .helpfulness import annotate_module, error_if_not_well_connected, Free, Needed, Giving, Dependent
from .pyrtlexceptions import PyrtlError
from .wire import WireVector, Input, Output
from .transform import replace_wire

_modIndexer = _NameIndexer("mod_tmp_")

class Module(ABC):
    @abstractmethod
    def definition(self, *args):
        pass

    def Input(self, bitwidth, name, sort=None, strict=False):
        if not self.in_definition:
            raise PyrtlError("Cannot create a module input outside of its definition")
        wv = _ModInput(bitwidth, name, self, sort, strict)
        self.input_dict[name] = wv
        return wv

    def Output(self, bitwidth, name, sort=None):
        if not self.in_definition:
            raise PyrtlError("Cannot create a module output outside of its definition")
        wv = _ModOutput(bitwidth, name, self, sort)
        self.output_dict[name] = wv
        return wv
    
    @property
    def inputs(self):
        return set(self.input_dict.values())

    @property
    def outputs(self):
        return set(self.output_dict.values())
    
    # TODO Problem if wire is a register...
    # TODO Make sure this wire isn't being used on the LHS of something
    def to_input(self, wire, name=""):
        """ (Experimental): Promote a wire to be a module's input """
        if not self.in_definition:
            raise PyrtlError("Cannot promote a wire to a module input outside of a module's definition")
        if not name:
            if wire.name.startswith("tmp"):
                raise PyrtlError(f"Trying to use the internal name of a wire ({wire.name}). "
                    "Either explicitly name the wire, or pass in a non-empty name to this method.")
        return self._to_mod_input(wire, name=name)

    # TODO Problem if wire is a register...
    # TODO Make sure this wire isn't being used on the RHS (e.g. other <<= this) of something,
    #      or allow it and make the necessary changes.
    def to_output(self, wire, name=""):
        """ (Experimental): Promote a wire to be a module's output """
        if not self.in_definition:
            raise PyrtlError("Cannot promote a wire to a module output outside of a module's definition")
        if not name:
            if wire.name.startswith("tmp"):
                raise PyrtlError(f"Trying to use the internal name of a wire ({wire.name}). "
                    "Either explicitly name the wire, or pass in a non-empty name to this method.")
        return self._to_mod_output(wire, name=name)

    def to_pyrtl_io(self):
        """ Sets this modules' input/output wires as the
            current block's input/output wires (normally
            only useful when running a simulation).
        """
        for w in self.inputs:
            w.to_pyrtl_input()
        for w in self.outputs:
            w.to_pyrtl_output()

    def _definition(self):
        self.in_definition = True
        self.definition()
        self.in_definition = False
    
    def _check_all_io_internally_connected(self):
        # Ensure that all _ModInput and _ModOutput wires
        # have been connected to some internal module logic
        src_dict, dest_dict = self.block.net_connections()
        for wire in self.inputs:
            if wire not in dest_dict:
                raise PyrtlError(f"Invalid module. Input {str(wire)} is not connected to any internal module logic.")
        for wire in self.outputs:
            if wire not in src_dict:
                raise PyrtlError(f"Invalid module. Output {str(wire)} is not connected to any internal module logic.")
    
    def _check_all_well_connected(self):
        # Call this if you want to check the well-connectedness at the end,
        # rather than after each connection during design elaboration; mostly
        # useful to seeing how long it takes, since checking well-connectedness
        # after each connection is made makes errors easier to report to the user.
        #ts = time.perf_counter()
        for mo in self.block.wirevector_subset(_ModOutput):
            error_if_not_well_connected(mo, None)
        #te = time.perf_counter()
        #print(f"Time to check: {te - ts}")

    def __init__(self, name="", block=None):
        # If the user supplies a name to their module's initializer and wants to set it via `self.name=`,
        # we need them to pass it into this initializer too. Not sure how to enforce this...
        self.name = name if name else _modIndexer.make_valid_string()
        self.block = block if block else working_block()
        self.block._add_module(self) # Must be done before _definition() for checking certain internal well-connected properties
        self.input_dict = {}
        self.output_dict = {}
        self._definition() # Must be done before annotating the module's inputs/outputs for helpfulness
        self._check_all_io_internally_connected() # Must be done before annotating module, because we rely on the module being connected internally
        #ts = time.perf_counter()
        annotate_module(self)
        #te = time.perf_counter()
        #print(f"Time to annotate: {te - ts}")
    
    def __getattr__(self, wirename):
        if wirename in self.__dict__['input_dict']:
            return self.__dict__['input_dict'][wirename]
        elif wirename in self.__dict__['output_dict']:
            return self.__dict__['output_dict'][wirename]
        else:
            input_list = ', '.join(f"'{wire._original_name}'" for wire in self.inputs)
            output_list = ', '.join(f"'{wire._original_name}'" for wire in self.outputs)
            raise AttributeError(
                f"Cannot get non-IO wirevector '{wirename}' from module.\n"
                "Make sure you spelled the wire name correctly, "
                "that you used 'self.Input' and 'self.Output' rather than "
                "'pyrtl.Input' and 'pyrtl.Output' to declare the IO wirevectors, "
                "and that you are accessing them from the correct module.\n"
                f"Available input wires are {input_list} and output wires are {output_list}.")
    
    def __setitem__(self, key, value):
        pass

    def __str__(self):
        s = ""
        s += f"Module '{self.__class__.__name__}'\n"
        s += f"  Inputs:\n"
        for wire in self.inputs:
            s += f"    {wire._original_name, str(wire.sort)}\n"
        s += f"  Outputs:\n"
        for wire in self.outputs:
            s += f"    {wire._original_name, str(wire.sort)}\n"
        return s

    def _to_mod_input(self, wire, name=None):
        name = name if name else wire.name
        new_wire = _ModInput(len(wire), name=name, module=self)
        self.input_dict[name] = new_wire
        replace_wire(wire, new_wire, new_wire, self.block)
        self.block.add_wirevector(new_wire)
        return new_wire
    
    def _to_mod_output(self, wire, name=None):
        name = name if name else wire.name
        new_wire = _ModOutput(len(wire), name=name, module=self)
        self.output_dict[name] = new_wire
        replace_wire(wire, new_wire, new_wire, self.block)
        self.block.add_wirevector(new_wire)
        return new_wire
    
    def _to_module_io(self, wire):
        if not isinstance(wire, (Input, Output)):
            raise PyrtlError("Can only convert PyRTL Input/Output "
                "wirevectors into module input/output")
        if isinstance(wire, Input):
            return self._to_mod_input(wire)
        elif isinstance(wire, Output):
            return self._to_mod_output(wire)

def module_from_block(block: Block = None, timing_out=None):
    block = working_block(block)
    class FromBlock(Module):
        def __init__(self):
            super().__init__(block=block)
        def definition(self):
            pass
    m = FromBlock()
    io = block.wirevector_subset((Input, Output))
    for wire in io:
        m._to_module_io(wire)
    m._check_all_io_internally_connected()
    if timing_out:
        ts = time.perf_counter()
    annotate_module(m)
    if timing_out:
        te = time.perf_counter()
        print(f"time to annotate (seconds): {te - ts}", file=timing_out)
    return m

class ModIOWire(WireVector):

    def __init__(self, bitwidth: int, name: str, module: Module):
        if not module:
            raise PyrtlError("Must supply a non-null module to a ModIOWire's constructor")
        self.module = module

        if not name:
            # Check this here because technically these are WireVectors, which accept
            # zero-length names, and we need a way to look them up later.
            raise PyrtlError("Must supply a non-empty name for a module's input/output wire")
        # Secretly store the given name, and pass in a blank name to the super
        # constructor so that a fresh temporary name is produced. This allows
        # two modules to be instantiated with same-named I/O wires without the
        # second overwriting the first.
        self._original_name = name
        super().__init__(bitwidth=bitwidth, name="", block=module.block)

    def __str__(self):
        return ''.join([self._original_name, '/', str(self.bitwidth), self._code])

    def is_driven(self):
        """ Check if this wire is being driven by another (i.e. self <<= other) """
        src_dict, _ = self.module.block.net_connections()
        # i.e. does this wire have any "sources" used to make it, meaning are there nets where it is a dest?
        return self in src_dict

    def is_driving(self):
        """ Check if this wire is driving any other wire (i.e. other <<= self) """
        _, dst_dict = self.module.block.net_connections()
        # i.e. does this wire have any "destinations", meaning are there nets where it is a source?
        return self in dst_dict

class _ModInput(ModIOWire):

    def __init__(self, bitwidth: int, name: str, module: Module, sort=None, strict=False):
        # sort can be the type, or an instance of the object with the awaited_by_set filled in
        # with either actual modio objects, or their names (in the case of an ascription)
        if sort and (sort not in (Free, Needed)) and (not isinstance(sort, (Free, Needed))):
            raise PyrtlError(f"Invalid sort ascription for input {name} "
                "(must provide either Free or Needed type name or instance)")
        self.sort = sort
        self.strict = strict
        super().__init__(bitwidth, name, module)
    
    def __ilshift__(self, other):
        """ self(_ModInput) <<= other """
        if self.module.in_definition:
            raise PyrtlError(f"Invalid module. Module input {str(self)} cannot "
                              "be used on the lhs of <<= while within a module definition.")
        # Note that OtherModule(_ModInput) <<= self is permitted to allow for nested modules,
        # because when that enters this method, OtherMoudle.in_definition will be False

        if len(self) != len(other):
            if self.strict:
                raise PyrtlError(f"Length of module input {str(self)} != length of {str(other)}, "
                    "and this module input has strict sizing set to True")
            # else:
            #     print(f"Warning: length of module input {str(self)} != length of {str(other)}. "
            #         "PyRTL will automatically match their sizes, so make sure you meant this.")
        
        if self.is_driven():
            raise PyrtlError(f"Attempted to connect to already-connected module input {str(self)})")

        # We could have other be a _ModOutput from another module,
        # or a _ModInput from a surrounding module (i.e. self is the nested module).
        # The "nested" case is always going to be outer _ModInput to nested _ModInput,
        # or nested _ModOutput to outer _ModOutput, and we actually don't need to check
        # these (proof should be following in the paper). Just check _ModInput <<= _ModOutput.
        # Actually, we need to check this in any case, because we could have the case where
        # w = _ModOutput * 3
        # _ModInput <<= w
        # meaning having an intermediate connection. Not a big deal, since the checking
        # will only traverse all the wires up to the nearest _ModOutput, after which time
        # it will skip over modules by just considering their requires/await sets
        error_if_not_well_connected(other, self)
        super().__ilshift__(other)
        return self
    
    def to_pyrtl_input(self, name=""):
        name = name if name else self._original_name
        w = Input(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        self.module.block.add_wirevector(w)
        # Note that the original _ModInput wire is still its parent module's internal information.
        # This may be useful to query different properties about the original wire.
        # _Don't_ return the new Input wire because we don't want anyone doing anything with it.

class _ModOutput(ModIOWire):

    def __init__(self, bitwidth: int, name: str, module: Module, sort=None):
        # sort can be the type, or an instance of the object with the requires_set filled in
        # with either actual modio objects, or their names (in the case of an ascription)
        if sort and (sort not in (Giving, Dependent)) and (not isinstance(sort, (Giving, Dependent))):
            raise PyrtlError(f"Invalid sort ascription for output {name} "
                "(must provide either Giving or Dependent type name or instance)")
        self.sort = sort
        super().__init__(bitwidth, name, module)

    def __ilshift__(self, other):
        """ self(_ModOutput) <<= other """
        if not self.module.in_definition:
            raise PyrtlError(f"Invalid module. Module output {str(self)} can only "
                              "be used on the lhs of <<= while within a module definition.")

        # This is checked in core.py:sanity_check_net()
        # if isinstance(other, _ModOutput) and self.module == other.module:
        #     # Check for equivalent modules because it's okay if it's a connection
        #     # from an outer module to a nested module.
        #     raise PyrtlError(f"Invalid module. Module output {str(other)} cannot be "
        #                       "used on the rhs of <<= while within a module definition.")

        if self.is_driven():
            raise PyrtlError(f"Attempted to connect to already-connected module output {str(self)})")

        # The only way to have access to a module's **unconnected** ModOuput wire is
        # when we're within a module's definition, meaning there is nothing to check yet.
        return super().__ilshift__(other)

    def to_pyrtl_output(self, name=""):
        name = name if name else self._original_name
        w = Output(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        self.module.block.add_wirevector(w)
        # Note that the original _ModOutput wire is still its parent module's internal information.
        # This may be useful to query different properties about the original wire.
        # _Don't_ return the new Output wire because we don't want anyone doing anything with it.