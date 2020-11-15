"""
Defines the Module class, an abstraction for encapsulating
logic behind well-defined input/outputs.
"""

# pylint: disable=no-member
# pylint: disable=unbalanced-tuple-unpacking
import math
import six

from .core import working_block, reset_working_block, _NameIndexer, LogicNet
from .corecircuits import as_wires, concat_list
from .memory import MemBlock
from .pyrtlexceptions import PyrtlError, PyrtlInternalError
from .transform import replace_wire
from .wire import WireVector, Register, Input, Output
from .wiresorts import annotate_module

_modIndexer = _NameIndexer("mod_")


def _reset_module_indexer():
    global _modIndexer
    _modIndexer = _NameIndexer(_modIndexer.internal_prefix)


def next_mod_name(name=""):
    if name == "":
        return _modIndexer.make_valid_string()
    elif name.startswith(_modIndexer.internal_prefix):
        raise PyrtlError(
            'Starting a module name with "%s" is reserved for internal use.'
            % _modIndexer.internal_prefix
        )
    elif name == "Top":
        raise PyrtlError('Module name "Top" is reserved for internal use.')
    else:
        return name


class Module(object):
    """ The Module superclass. All user-defined modules must be a subclass
        of this class.
    """

    def __init__(self, name="", block=None):
        """ Create a module, which represents the encapsulation of logic
            behind strict input/output wires. The hardware to be elaborated
            must be defined by the concrete class via the 'definition' function.

            :param name: Name to give this module
            :param block: Block to which the module belongs
        """
        self.inputs = set()
        self.outputs = set()
        self.submodules = set()
        self.inputs_by_name = {}  # map from input.original_name to wire (for performance)
        self.outputs_by_name = {}  # map from output.original_name to wire (for perfomance)
        self.submodules_by_name = {}  # map from submodule.name to submodule (for performance)
        self.supermodule = None
        self._in_definition = False
        self.wires = set()
        self.name = next_mod_name(name)
        self.block = working_block(block)
        self.block._add_module(self)
        self._definition()
        self.validity_check()
        annotate_module(self)

    def _definition(self):
        self._register_if_submodule()
        self.block._current_module_stack.append(self)
        self._in_definition = True
        self.definition()
        self._in_definition = False
        self.block._current_module_stack.pop()

    def definition(self):
        """ Each module subclass needs to provide the code that should be
            elaborated when the module is instantiated. This is like the
            `main` method of the module.
        """
        raise PyrtlError('Module subclasses must supply a `definition` method')

    @classmethod
    def from_block(cls, block=None):
        """ Convert a given block into a module. Its inputs and outputs become
            the module's inputs/outputs. All existing modules become
            submodules of this new toplevel module.

            I believe that due to the way we have checks occurring when nets
            are added, the block will only be valid at this point if they
            already hold, which is good. Now we're going to create this
            module object inside-out, as it were.
        """
        self = cls.__new__(cls)
        self.inputs = set()
        self.outputs = set()
        self.submodules = set()
        self.inputs_by_name = {}  # map from input.original_name to wire (for performance)
        self.outputs_by_name = {}  # map from output.original_name to wire (for perfomance)
        self.submodules_by_name = {}  # map from submodule.name to submodule (for performance)
        self.supermodule = None
        self.wires = set()
        self.name = "Top"
        self.block = working_block(block)
        self.block._add_module(self)

        # The rest is essentially our `definition` method,
        # i.e converting the block's existing logic into this module's
        self._in_definition = True
        self.block._current_module_stack.append(self)

        # For all top-level wires (i.e. not already in an existing module),
        # set their owning module to this one
        for wire in self.block.wirevector_set:
            if not wire.module:
                wire.module = self

        # All existing top-level modules now have the new module as their supermodule
        for mod in self.block.toplevel_modules:
            assert not mod.supermodule
            if mod is not self:
                mod.supermodule = self
                self.submodules.add(mod)
                self.submodules_by_name[mod.name] = mod

        # Convert the inputs and outputs!
        for orig_wire in self.block.wirevector_subset(Input):
            minput = self.Input(orig_wire.bitwidth, orig_wire.name)
            replace_wire(orig_wire, minput, minput, minput.module.block)
        for orig_wire in self.block.wirevector_subset(Output):
            moutput = self.Output(orig_wire.bitwidth, orig_wire.name)
            replace_wire(orig_wire, moutput, moutput, moutput.module.block)

        self.block._current_module_stack.pop()
        self._in_definition = False

        self.validity_check()

        import time
        _ts = time.perf_counter()
        annotate_module(self)
        _te = time.perf_counter()
        return self, _te - _ts  # Remove after testing

    def Input(self, bitwidth, name):
        if not self._in_definition:
            raise PyrtlError("Cannot create a module input outside of the module's definition")
        w = _ModInput(bitwidth, name, self)
        self.inputs.add(w)
        self.inputs_by_name[w._original_name] = w
        return w

    def Output(self, bitwidth, name):
        if not self._in_definition:
            raise PyrtlError("Cannot create a module output outside of the module's definition")
        w = _ModOutput(bitwidth, name, self)
        self.outputs.add(w)
        self.outputs_by_name[w._original_name] = w
        return w

    def _register_if_submodule(self):
        if self.block.current_module:
            self.supermodule = self.block.current_module
            self.supermodule.submodules.add(self)
            self.supermodule.submodules_by_name[self.name] = self

    def add_wire(self, wire):
        self.wires.add(wire)

    def to_block_io(self):
        """ Sets this module's input/output wires as the current block's I/O """
        if self.supermodule:
            raise PyrtlError(
                'Can only promote the io wires of top-level modules to block io. '
                '"%s" is not a top-level module (is a submodule of "%s").'
                % (self.name, self.supermodule)
            )
        for w in self.inputs:
            w.to_block_input()
        for w in self.outputs:
            w.to_block_output()

    def validity_check(self):
        # At least one _ModOutput
        if not self.outputs:
            raise PyrtlError("Module must have at least one output.")

        # All _ModInput and _ModOutput names are unique (especially important since we use those
        # names as attributes for accessing them via the dot operator on the module).
        io_names_set = set(io._original_name for io in self.inputs.union(self.outputs))
        if len(self.inputs.union(self.outputs)) != len(io_names_set):
            io_names_list = sorted([io._original_name for io in self.inputs.union(self.outputs)])
            for io in io_names_set:
                io_names_list.remove(io)
            raise PyrtlError('Duplicate names found for the following different module '
                             'input/output wires: %s (make sure you are not using "%s" '
                             'as a prefix because that is reserved for internal use).' %
                             (repr(io_names_list), _modIndexer.internal_prefix))

        src_dict, dest_dict = self.block.net_connections()

        # All _ModInput and _ModOutput wires have been connected
        for wire in self.inputs:
            if wire not in dest_dict:
                raise PyrtlError('Invalid module. Input "%s" is not connected '
                                 'to any internal module logic.' % str(wire))

        # All _ModOutput wires have been connected
        for wire in self.outputs:
            if wire not in src_dict:
                raise PyrtlError('Invalid module. Output "%s" is not connected '
                                 'to any internal module logic.' % str(wire))

        # Only track wires we own
        for wire in self.wires:
            if not hasattr(wire, 'module'):
                raise PyrtlInternalError(
                    'Wire "%s" does not have a "module" attribute.'
                    % str(wire)
                )
            if wire.module != self:
                raise PyrtlError(
                    'Wire %s is not owned by module %s but is present in its wire set'
                    % (str(wire), self.name)
                )

    def __str__(self):
        """ Print out the wire sorts for each input and output """
        s = "Module '%s'\n" % self.__class__.__name__
        s += "  Inputs:\n"
        for wire in sorted(self.inputs, key=lambda w: w._original_name):
            s += "    %s\n" % repr({wire._original_name: str(wire.sort)})
        s += "  Outputs:\n"
        for wire in sorted(self.outputs, key=lambda w: w._original_name):
            s += "    %s\n" % repr({wire._original_name: str(wire.sort)})
        return s

    def __getattr__(self, name):
        """ You can access a module's input/output wires like 'module.wire_original_name'.
            You can also access a module's submodules like 'module.submodule_name'.
        """
        if name in self.__dict__['inputs_by_name']:
            return self.__dict__['inputs_by_name'][name]
        elif name in self.__dict__['outputs_by_name']:
            return self.__dict__['outputs_by_name'][name]
        elif name in self.__dict__['submodules_by_name']:
            return self.__dict__['submodules_by_name'][name]
        else:
            inputs = [str(i) for i in self.inputs]
            outputs = [str(o) for o in self.outputs]
            submodules = [m.name for m in self.submodules]
            raise AttributeError(
                'Cannot get non-IO wirevector/submodule "%s" from module "%s".\n'
                'Make sure you spelled the wire name correctly, '
                'that you used "self.Input" and "self.Output" rather than '
                '"pyrtl.Input" and "pyrtl.Output" to declare the IO wirevectors, '
                'and that you are accessing it from the correct module.\n'
                'Available input wires are %s and output wires are %s.\n'
                'Available submodules are %s.' %
                (name, self.name, str(inputs), str(outputs), str(submodules)))


def module_from_block(block=None):
    return Module.from_block(block)[0]  # TODO add [0] when not doing timing tests


class _ModIO(WireVector):
    """ The base class for module inputs/outputs """

    def __init__(self, bitwidth, name, module):
        """ We purposefully hide the original name so that multiple instantiations of the same
            module with named wires don't conflict. You access these wires via module.wire_name,
            where wire_name is the wire's original_name given in the initializer here.
        """
        if not name:
            raise PyrtlError("Must supply a non-empty name for a module's input/output wire")
        self._original_name = name
        self.sort = None
        self.module = module
        super(_ModIO, self).__init__(bitwidth)

    def __str__(self):
        return "%s/%d%s[%s]" % (self._original_name, self.bitwidth, self._code, self.module.name)


class _ModInput(_ModIO):
    """ A WireVector class for specifying input to a single module """

    _code = "I"

    def to_block_input(self, name=""):
        """ Access this wire via a block Input """
        # Instead of replacing the wire, which would break the invariant
        # that you can only connect to a module's internal wires via the module's input/output,
        # in addition to the invariant that pyrtl.Outputs cannot be arguments to nets (which
        # _ModOutputs can be), create a new block Input/Output by the same name and connect!
        name = name if name else self._original_name
        w = Input(len(self), name=name, block=self.module.block)
        self <<= w


class _ModOutput(_ModIO):
    """ A WireVector class for specifying output from a single module """

    _code = "O"

    def to_block_output(self, name=""):
        """ Access this wire via a block Output """
        # See notes in `to_block_input`
        name = name if name else self._original_name
        w = Output(len(self), name=name, block=self.module.block)
        w <<= self
