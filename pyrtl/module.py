from abc import ABC, abstractmethod
from typing import Tuple, Set
from .core import working_block, Block
from .helpfulness import annotate_module, error_if_not_well_connected
from .pyrtlexceptions import PyrtlError
from .wire import WireVector, Input, Output
from .transform import replace_wire

class Module(ABC):
    @abstractmethod
    def definition(self, *args):
        pass

    def Input(self, bitwidth, name):
        wv = ModInput(bitwidth, name, self)
        self.input_dict[name] = wv
        return wv

    def Output(self, bitwidth, name):
        wv = ModOutput(bitwidth, name, self)
        self.output_dict[name] = wv
        return wv
    
    def inputs(self):
        return set(self.input_dict.values())

    def outputs(self):
        return set(self.output_dict.values())

    def to_pyrtl_io(self):
        """ Sets this modules' input/output wires as the
            current block's input/output wires (normally
            only useful when running a simulation).
        """
        for w in self.inputs():
            w.to_pyrtl_input()
        for w in self.outputs():
            w.to_pyrtl_output()

    def _definition(self):
        self.in_definition = True
        self.definition()
        self.in_definition = False
    
    def _check_all_io_internally_connected(self):
        # Ensure that all ModInput and ModOutput wires
        # have been connected to some internal module logic
        src_dict, dest_dict = self.block.net_connections()
        for wire in self.inputs():
            if wire not in dest_dict:
                raise PyrtlError(f"Invalid module. Input {str(wire)} is not connected to any internal module logic.")
        for wire in self.outputs():
            if wire not in src_dict:
                raise PyrtlError(f"Invalid module. Output {str(wire)} is not connected to any internal module logic.")

    def __init__(self, name="", block=None):
        # If the user supplies a name to their module's initializer and wants to set it via `self.name=`,
        # we need them to pass it into this initializer too. Not sure how to enforce this...
        self.name = name
        self.block = block if block else working_block()
        self.input_dict = {}
        self.output_dict = {}
        self._definition() # Must be done before annotating the module's inputs/outputs for helpfulness
        self._check_all_io_internally_connected() # Must be done before annotating module, because we rely on the module being connected internally
        annotate_module(self)
    
    def __getitem__(self, wirename):
        if wirename in self.input_dict:
            return self.input_dict[wirename]
        elif wirename in self.output_dict:
            return self.output_dict[wirename]
        else:
            raise PyrtlError(
                f"Cannot get non-IO wirevector {wirename} from module.\n"
                "Make sure you spelled the wire name correctly, "
                "that you used 'self.Input' and 'self.Output' rather than "
                "'pyrtl.Input' and 'pyrtl.Output' to declare the IO wirevectors, "
                "and that you are accessing them from the correct module.")
    
    def __setitem__(self, key, value):
        pass

    def __str__(self):
        s = ""
        s += f"Module '{self.__class__.__name__}'\n"
        s += f"  Inputs:\n"
        for wire in self.input_dict.values():
            s += f"    {wire.original_name, str(wire.sort)}\n"
        s += f"  Outputs:\n"
        for wire in self.output_dict.values():
            s += f"    {wire.original_name, str(wire.sort)}\n"
        return s
    
    def _to_module_io(self, wire):
        if not isinstance(wire, (Input, Output)):
            raise PyrtlError("Can only convert PyRTL Input/Output "
                "wirevectors into module input/output")
        if isinstance(wire, Input):
            new_wire = ModInput(len(wire), name=wire.name, module=self)
            self.input_dict[wire.name] = new_wire
        elif isinstance(wire, Output):
            new_wire = ModOutput(len(wire), name=wire.name, module=self)
            self.output_dict[wire.name] = new_wire

        replace_wire(wire, new_wire, new_wire, self.block)
        self.block.add_wirevector(new_wire)
        return new_wire

def module_from_block(block: Block = None):
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
    annotate_module(m)
    return m

class ModIOWire(WireVector):

    def __init__(self, bitwidth: int, name: str, module: Module):
        self.module = module
        if not name:
            # Check this here because technically these are WireVectors, which accept
            # zero-length names, and we need a way to look them up later.
            raise PyrtlError("Must supply a non-empty name for a module's input/output wire")
        # Secretly store the given name, and pass in a blank name to the super
        # constructor so that a fresh temporary name is produced. This allows
        # two modules to be instantiated with same-named I/O wires without the
        # second overwriting the first.
        self.original_name = name
        super().__init__(bitwidth=bitwidth, name="", block=module.block)

    def __str__(self):
        return ''.join([self.original_name, '/', str(self.bitwidth), self._code])

    @abstractmethod
    def externally_connected(self) -> bool:
        pass

class ModInput(ModIOWire):
    
    def __ilshift__(self, other):
        """ self(ModInput) <<= other """
        if self.module.in_definition:
            raise PyrtlError(f"Invalid module. Module input {str(self)} cannot "
                              "be used on the lhs of <<= while within a module definition.")

        # We could have other be a ModOutput from another module,
        # or a ModInput from a surrounding module (i.e. self is the nested module).
        # The "nested" case is always going to be outer ModInput to nested ModInput,
        # or nested ModOutput to outer ModOutput, and we actually don't need to check
        # these (proof should be following in the paper). Just check ModInput <<= ModOutput.
        # Actually, we need to check this in any case, because we could have the case where
        # w = ModOutput * 3
        # ModInput <<= w
        # meaning having an intermediate connection. Not a big deal, since the checking
        # will only traverse all the wires up to the nearest ModOutput, after which time
        # it will skip over modules by just considering their requires/await sets
        error_if_not_well_connected(self, other)
        super().__ilshift__(other)
        return self
    
    def to_pyrtl_input(self, name=""):
        name = name if name else self.original_name
        w = Input(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        self.module.block.add_wirevector(w)
        # Note that the original ModInput wire is still its parent module's internal information.
        # This may be useful to query different properties about the original wire.
        # _Don't_ return the new Input wire because we don't want anyone doing anything with it.
    
    def externally_connected(self):
        """ Check if this Input wire is connected to any external (outside of module) wires """
        src_dict, _ = self.module.block.net_connections()
        return self in src_dict

class ModOutput(ModIOWire):

    def __ilshift__(self, other):
        """ self(ModOutput) <<= other """
        if not self.module.in_definition:
            raise PyrtlError(f"Invalid module. Module output {str(self)} can only "
                              "be used on the lhs of <<= while within a module definition.")

        if isinstance(other, ModOutput) and self.module == other.module:
            # Check for equivalent modules because it's okay if it's a connection
            # from an outer module to a nested module.
            raise PyrtlError(f"Invalid module. Module output {str(other)} cannot be "
                              "used on the rhs of <<= while within a module definition.")

        # The only way to have access to a module's **unconnected** ModOuput wire is
        # when we're within a module's definition, meaning there is nothing to check yet.
        return super().__ilshift__(other)

    def to_pyrtl_output(self, name=""):
        name = name if name else self.original_name
        w = Output(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        self.module.block.add_wirevector(w)
        # Note that the original ModOutput wire is still its parent module's internal information.
        # This may be useful to query different properties about the original wire.
        # _Don't_ return the new Output wire because we don't want anyone doing anything with it.

    def externally_connected(self):
        """ Check if this Output wire is connected to any external (outside of module) wires """
        _, dst_dict = self.module.block.net_connections()
        return self in dst_dict