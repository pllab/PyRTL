# pylint: disable=no-member
# pylint: disable=unbalanced-tuple-unpacking
from abc import ABC, abstractmethod
import math
import six

from .core import working_block, reset_working_block, _NameIndexer
from .corecircuits import as_wires, concat_list
from .memory import MemBlock
from .pyrtlexceptions import PyrtlError
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
    else:
        return name


class Module(ABC):

    def __init__(self, name="", block=None):
        self.inputs = set()
        self.outputs = set()
        self.inputs_by_name = {}  # map from input.original_name to wire (for performance)
        self.outputs_by_name = {}  # map from output.original_name to wire (for perfomance)
        self.submodules = set()
        self.supermodule = None
        self.name = next_mod_name(name)
        self.block = working_block(block)
        self.block._add_module(self)
        self.definition()
        self.sanity_check()
        annotate_module(self)

    @abstractmethod
    def definition(self):
        """ Each module subclass needs to provide the code that should be
            elaborated when the module is instantiated. This is like the
            `main` method of the module.
        """
        pass

    def Input(self, bitwidth, name):
        w = _ModInput(bitwidth, name, self)
        self.inputs.add(w)
        self.inputs_by_name[w._original_name] = w
        return w

    def Output(self, bitwidth, name):
        w = _ModOutput(bitwidth, name, self)
        self.outputs.add(w)
        self.outputs_by_name[w._original_name] = w
        return w

    def submod(self, mod):
        """ Register the module 'mod' as a submodule of this one """
        # TODO I'm not sure if I love this approach
        self.submodules.add(mod)
        mod.supermodule = self
        return mod

    def wires(self):
        """ Get all wires contained in this module (except those included in submodules) """
        # TODO or change it to a 'logic' function that returns nets within this module?
        pass

    def to_block_io(self):
        """ Sets this module's input/output wires as the current block's I/O """
        for w in self.inputs:
            w.to_block_input()
        for w in self.outputs:
            w.to_block_output()

    def sanity_check(self):
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

        # All _ModInput and _ModOutput wires have been connected to some internal module logic.
        for wire in self.inputs:
            if wire not in dest_dict:
                raise PyrtlError('Invalid module. Input "%s" is not connected '
                                 'to any internal module logic.' % str(wire))
        for wire in self.outputs:
            if wire not in src_dict:
                raise PyrtlError('Invalid module. Output "%s" is not connected '
                                 'to any internal module logic.' % str(wire))

        # This _ModInputs aren't used as destinations to nets within module
        # (I don't think is necessary actually)
        # for wire in self.inputs:
        #     if wire in src_dict:
        #         raise PyrtlError(
        #             'Invalid module. Module input "%s" cannot be '
        #             'used as a destination to a net (%s) within a module definition.'
        #             % (str(wire), str(src_dict[wire]))
        #         )

        # This _ModOutputs aren't used as arguments to nets within module,
        # (I don't think this is necessary actually).
        # for wire in self.outputs:
        #     if wire in dest_dict:
        #         raise PyrtlError(
        #             'Invalid module. Module output "%s" cannot be '
        #             'used as an argument to a net (%s) within a module definition.'
        #             % (str(wire), str(dest_dict[wire]))
        #         )

        # Check that all internal wires are encapsulated,
        # meaning they don't directly connect to any wires defined outside the module.
        # TODO

    def __str__(self):
        """ Print out the wire sorts for each input and output """
        s = "Module '%s'\n" % self.__class__.__name__
        s += "  Inputs:\n"
        for wire in sorted(self.inputs, key=lambda w: w._original_name):
            s += "    %s\n" % repr({wire._original_name, str(wire.sort)})
        s += "  Outputs:\n"
        for wire in sorted(self.outputs, key=lambda w: w._original_name):
            s += "    %s\n" % repr({wire._original_name, str(wire.sort)})
        return s

    def __getattr__(self, name):
        if name in self.__dict__['inputs_by_name']:
            return self.__dict__['inputs_by_name'][name]
        elif name in self.__dict__['outputs_by_name']:
            return self.__dict__['outputs_by_name'][name]
        else:
            inputs = [str(i) for i in self.inputs]
            outputs = [str(o) for o in self.outputs]
            raise AttributeError(
                'Cannot get non-IO wirevector "%s" from module.\n'
                'Make sure you spelled the wire name correctly, '
                'that you used "self.Input" and "self.Output" rather than '
                '"pyrtl.Input" and "pyrtl.Output" to declare the IO wirevectors, '
                'and that you are accessing it from the correct module.\n'
                'Available input wires are %s and output wires are %s.' %
                (name, str(inputs), str(outputs)))


class _ModIO(WireVector):
    def __init__(self, bitwidth, name, module):
        if not name:
            raise PyrtlError("Must supply a non-empty name for a module's input/output wire")
        self._original_name = name
        self.sort = None
        self.module = module
        super().__init__(bitwidth)

    def __str__(self):
        return "%s/%d%s(%s)" % (self._original_name, self.bitwidth, self._code, self.module.name)


class _ModInput(_ModIO):
    _code = "I"

    def to_block_input(self, name=""):
        """ Make this wire a block Input wire """
        name = name if name else self._original_name
        w = Input(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        # At this point, `self` has been removed from the block,
        # but is present in `self.module.inputs`
        self.module.block.add_wirevector(w)


class _ModOutput(_ModIO):
    _code = "O"

    def to_block_output(self, name=""):
        """ Make this wire a block Output wire """
        name = name if name else self._original_name
        w = Output(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        # At this point, `self` has been removed from the block,
        # but is present in `self.module.outputs`
        self.module.block.add_wirevector(w)
