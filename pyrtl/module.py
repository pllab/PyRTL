
from abc import ABC, abstractmethod
from typing import Tuple, Set
import pyrtl
from .helpfulness import annotate_module, error_if_not_well_connected

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
    
    def check_all_io_internally_connected(self):
        # Ensure that all ModInput and ModOutput wires
        # have been connected to some internal module logic
        src_dict, dest_dict = self.block.net_connections()
        for wire in self.inputs():
            if wire not in dest_dict:
                raise pyrtl.PyrtlError(f"Invalid module. Input {str(wire)} is not connected to any internal module logic.")
        for wire in self.outputs():
            if wire not in src_dict:
                raise pyrtl.PyrtlError(f"Invalid module. Output {str(wire)} is not connected to any internal module logic.")

    def __init__(self, block=None):
        self.block = block if block else pyrtl.working_block()
        self.input_dict = {}
        self.output_dict = {}
        self.definition() # Must be done before annotating the module's inputs/outputs for helpfulness
        self.check_all_io_internally_connected() # Must be done before annotating module, because we rely on the module being connected internally
        annotate_module(self)
    
    def __getitem__(self, wirename):
        if wirename in self.input_dict:
            return self.input_dict[wirename]
        elif wirename in self.output_dict:
            return self.output_dict[wirename]
        else:
            raise pyrtl.PyrtlError(
                "Cannot get non-IO wirevector from module.\n"
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
            s += f"    {wire.name, str(wire.sort)}\n"
        s += f"  Outputs:\n"
        for wire in self.output_dict.values():
            s += f"    {wire.name, str(wire.sort)}\n"
        return s


class ModIOWire(pyrtl.WireVector):

    def __init__(self, bitwidth: int, name: str, module: Module):
        self.module = module
        if not name:
            # Check this here because technically these are WireVectors, which accept
            # zero-length names, and we need a way to look them up later.
            raise pyrtl.PyrtlError("Must supply a non-empty name for a module's input/output wire")
        super().__init__(bitwidth, name, module.block)


class ModInput(ModIOWire):
    
    def __ilshift__(self, other):
        # We could have other be a ModOutput from another module,
        # or a ModInput from a surrounding module (i.e. self is the nested module).
        # The "nested" case is always going to be outer ModInput to nested ModInput,
        # or nested ModOutput to outer ModOutput, and we actually don't need to check
        # these (proof should be following in the paper). Just check ModInput <<= ModOutput.
        if isinstance(other, (ModOutput)):
            error_if_not_well_connected(self, other)
        super().__ilshift__(other)
        return self
    
    def to_pyrtl_input(self):
        w = pyrtl.Input(len(self), name=self.name, block=self.module.block)
        pyrtl.replace_wire(self, w, w, self.module.block)
        self.module.block.add_wirevector(w)

class ModOutput(ModIOWire):

    def __ilshift__(self, other):
        # The only way to have access to a module's **unconnected** ModOuput wire is
        # when we're within a module's definition, meaning there is nothing to check yet.
        return super().__ilshift__(other)

    def to_pyrtl_output(self):
        w = pyrtl.Output(len(self), name=self.name, block=self.module.block)
        pyrtl.replace_wire(self, w, w, self.module.block)
        self.module.block.add_wirevector(w)