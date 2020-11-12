# pylint: disable=no-member
# pylint: disable=unbalanced-tuple-unpacking
from abc import ABC, abstractmethod
import math
import six

from .wire import WireVector, Register, Input, Output
from .memory import MemBlock
from .core import working_block, reset_working_block, _NameIndexer
from .corecircuits import as_wires, concat_list
from .wiresorts import annotate_module
from .transform import replace_wire

_modIndexer = _NameIndexer("mod_")

def _reset_module_indexer():
    global _modIndexer
    _modIndexer = _NameIndexer("mod_")

class Module(ABC):
    def __init__(self, name="", block=None):
        self.inputs = set()
        self.outputs = set()
        self.block = working_block(block)
        self.name = name if name else _modIndexer.make_valid_string()
        self.definition()
        annotate_module(self)
    
    @abstractmethod
    def definition(self):
        pass

    def Input(self, bitwidth, name):
        w = _ModInput(bitwidth, name, self)
        self.inputs.add(w)
        setattr(self, name, w)
        return w
    
    def Output(self, bitwidth, name):
        w = _ModOutput(bitwidth, name, self)
        self.outputs.add(w)
        setattr(self, name, w)
        return w
    
    def wires(self):
        """ Get all wires contained in this module, (except those included in submodules) """
        pass

    def submodules(self):
        pass

    def to_block_io(self):
        """ Sets this module's input/output wires as the current block's I/O """
        for w in self.inputs:
            w.to_block_input()
        for w in self.outputs:
            w.to_block_output()
    
    def __str__(self):
        """ Print out the wire sorts for each input and output """
        s = f"Module '{self.__class__.__name__}'\n"
        s += f"  Inputs:\n"
        for wire in sorted(self.inputs, key=lambda w: w._original_name):
            s += f"    {wire._original_name, str(wire.sort)}\n"
        s += f"  Outputs:\n"
        for wire in sorted(self.outputs, key=lambda w: w._original_name):
            s += f"    {wire._original_name, str(wire.sort)}\n"
        return s

class _ModIO(WireVector):
    def __init__(self, bitwidth, name, module):
        self._original_name = name
        self.sort = None
        self.module = module
        super().__init__(bitwidth)

class _ModInput(_ModIO):
    def to_block_input(self, name=""):
        """ Make this wire a block Input wire """
        name = name if name else self._original_name
        w = Input(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        # At this point, `self` has been removed from the block, but is present in `self.module.inputs`
        self.module.block.add_wirevector(w)

class _ModOutput(_ModIO):
    def to_block_output(self, name=""):
        """ Make this wire a block Output wire """
        name = name if name else self._original_name
        w = Output(len(self), name=name, block=self.module.block)
        replace_wire(self, w, w, self.module.block)
        # At this point, `self` has been removed from the block, but is present in `self.module.outputs`
        self.module.block.add_wirevector(w)