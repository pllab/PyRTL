# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=line-too-long

import abc
from collections import namedtuple
from functools import reduce
from typing import Set

from .pyrtlexceptions import PyrtlError
from .core import working_block
from .wire import Const, WireVector, Register, Input, Output
from .memory import MemBlock, RomBlock

Verbose = False

class InputSort(abc.ABC):
    pass

class Free(InputSort):
    def __init__(self, wire):
        self.wire = wire
        self.awaited_by_set = set()

    def __str__(self):
        return "Free"

class Needed(InputSort):
    def __init__(self, wire, awaited_by_set):
        from .module import ModOutput
        self.wire = wire
        self.awaited_by_set = awaited_by_set
        # Sanity check
        for w in self.awaited_by_set:
            assert(isinstance(w, ModOutput))

    def __str__(self):
        wns = ", ".join(map(str, self.awaited_by_set))
        return f"Needed (needed by: {wns})"

class OutputSort(abc.ABC):
    pass

class Giving(OutputSort):
    def __init__(self, wire):
        self.wire = wire
        self.requires_set = set()

    def __str__(self):
        return "Giving"

class Dependent(OutputSort):
    def __init__(self, wire, requires_set):
        from .module import ModInput
        self.wire = wire
        self.requires_set = requires_set
        # Sanity check
        for w in self.requires_set:
            assert(isinstance(w, ModInput))

    def __str__(self):
        wns = ", ".join(map(str, self.requires_set))
        return f"Dependent (depends on: {wns})"

# Possibly several things to make this more efficient:
# - check for ill-connectedness during the process, not just after getting the reachability set
# - cache the results
def error_if_not_well_connected(from_wire, to_wire):
    # NOTE: this assumes everythings is in the same working block.
    from .module import ModInput, ModOutput
        
    if not isinstance(from_wire, ModOutput):
        # get all the closest ModOutputs that combinationally connect to this regular wire
        from_output_wires = set(w for w in _backward_combinational_reachability(from_wire) if isinstance(w, ModOutput))
    else:
        from_output_wires = {from_wire}

    if not isinstance(to_wire, ModInput):
        # get all the closest ModInputs that this wire combinationally connects to
        to_input_wires = set(w for w in _forward_combinational_reachability(to_wire) if isinstance(w, ModInput))
    else:
        to_input_wires = {to_wire}
    
    # Since we have a call in WireVector.__ilshift__ (i.e. connecting
    # arbitrary wires), rather than just when connecting to known ModInputs,
    # we need to make sure we're not inside a module definition.
    # This function only works when analyzing connections between modules
    # that have already been analyzed.
    for io_wire in from_output_wires.union(to_input_wires):
        if io_wire.module.in_definition:
            return

    for from_wire in from_output_wires:
        assert isinstance(from_wire, ModOutput)
        assert isinstance(from_wire.sort, (Giving, Dependent))

        for to_wire in to_input_wires:
            assert isinstance(to_wire, ModInput)
            assert isinstance(to_wire.sort, (Free, Needed))

            # from_wire is from module 1
            # to_wire is from module 2
            #
            # for each input wire 'required_wire' required by 'from_wire' (all of which are inputs to module 1):
            #   for each output wire 'awaiting_wire' awaiting 'to_wire' (all of which are outputs of module 2):
            #       ensure 'awaiting_wire' is **not** transitively combinationally connected to 'required_wire'
            if isinstance(to_wire.sort, Needed) and isinstance(from_wire.sort, Dependent):
                if to_wire in from_wire.sort.requires_set or from_wire in to_wire.sort.awaited_by_set:
                    # Trivial loop (we need this check if we're *not* inserting the connection
                    # before checking; otherwise the check below suffices)
                    raise PyrtlError(
                        "Connection error!\n"
                        f"{str(to_wire)} <<= {str(from_wire)}\n")
                for required_wire in from_wire.sort.requires_set:
                    for awaiting_wire in to_wire.sort.awaited_by_set:
                        assert isinstance(required_wire, ModInput)
                        assert isinstance(awaiting_wire, ModOutput)

                        descendants = _forward_combinational_reachability(awaiting_wire, transitive=True)
                        descendants.add(awaiting_wire)
                        if required_wire in descendants:
                            raise PyrtlError("Connection error!\n" f"{str(to_wire)} <<= {str(from_wire)}\n")

def annotate_module(module):
    for wire in module.inputs().union(module.outputs()):
        sort = get_wire_sort(wire, module)
        # If wire.sort was ascribed, check it and report if not matching
        # We have the user provide the classname of the sort, rather
        # than an actual instance of the class.
        if wire.sort and not isinstance(sort, wire.sort):
            raise PyrtlError(
                f"Unmatched sort ascription on wire {str(wire)}.\n"
                f"User provided {wire.sort.__name__}\n"
                f"But computed {str(sort)}")
        wire.sort = sort

def get_wire_sort(wire, module):
    from .module import ModInput, ModOutput

    if isinstance(wire, ModInput):
        # Get its forward reachability (wires that 'wire' combinationally affects WITHIN this module)...
        forward = _forward_combinational_reachability(wire, module.block)
        # ... and then just filter for the module outputs that wire affects
        affects = set(w for w in forward if w in module.outputs())
        if affects:
            return Needed(wire, affects)
        return Free(wire)
    elif isinstance(wire, ModOutput):
        # Get its backward reachbility (wires that 'wire' combinationally depends on WITHIN this module)...
        backward = _backward_combinational_reachability(wire, module.block)
        # ... and then jus tilfter for the module inputs it depends on
        depends = set(w for w in backward if w in module.inputs())
        if depends:
            return Dependent(wire, depends)
        return Giving(wire)
    else:
        raise PyrtlError("Only get wire sorts of inputs/outputs")

# For forward combinational reachability, if the wire we're checking
# is a ModInput, then get all the wires it affects combinationally inside its module.
# Otherwise, transitively go forward, and when you reach a ModInput,
# continue with the ModOutput wires in that ModInput's awaited_by set
# (which has already been computed once per other module),
# so we don't descend into the module itself, theoretically saving time
# by not having to navigate any modules' netlist.
def _forward_combinational_reachability(wire, transitive=False, block=None) -> Set[WireVector]:
    """ Get the wires that 'wire' combinationally affects

        :param wire: wire whose combinationally-reachable descendant wires we want to find
        :param block: block to which the wire belongs

        Handles if there are combinational loops
    """
    from .module import ModInput 
    if isinstance(wire, (Const, Register, MemBlock, RomBlock, Output)):
        return {wire}
    
    block = working_block(block)

    # dest_dict: the map from wire to the nets (plural) where that wire
    # is a source (i.e. it helps us find the wires that this wire affects)
    # i.e. for net in dest_dict[wire]:
    #        assert wire in net.args
    _, dest_dict = block.net_connections()

    # wire is Input or normal wire
    affects = set()
    tocheck = set()

    if wire in dest_dict:
        for net in dest_dict[wire]:
            if net.dests:
                tocheck.add(net.dests[0])

    while tocheck:
        w = tocheck.pop()
        if w in affects:
            continue  # already checked, possible with diamond dependency

        affects.add(w)

        if isinstance(w, ModInput) and not transitive:
            continue

        if (wire is not w) and isinstance(w, ModInput):
            # If we're at a ModInput and it's not the original wire we're checking
            # forward reachability for, then jump over the module and just get the
            # awaited_by_set.
            for mod_output in w.sort.awaited_by_set:
                tocheck.add(mod_output)

        elif not isinstance(w, (Output, Const, Register, MemBlock, RomBlock)):
            if w not in dest_dict:
                if Verbose:
                    print(f"Warning: {w} not in dest_dict")
            else:
                for net in dest_dict[w]:
                    if net.dests:
                        tocheck.add(net.dests[0])
    return affects

# For backward combinational reachability, if the wire we're checking
# is a ModOutput, then get all the wires it depends on combinationally inside its module.
# Otherwise, transitively go backward, and when you reach a ModOutput,
# continue with the ModInput wires in that ModOutput's depends set
# (which has already been computed once per other module),
# so we don't descend into the module itself, theoretically saving time
# by not having to navigate any modules' netlist.
def _backward_combinational_reachability(wire, transitive=False, block=None):
    """ Get the wires that wire combinationally depends on

        :param wire: output wire whose combinationally-reachable ancestor wires we want to find
        :param block: block to which the wire belongs

        Handles if there are combinational loops
    """

    from .module import ModOutput
    if isinstance(wire, (Const, Register, MemBlock, RomBlock, Input)):
        return {wire}
    
    block = working_block(block)
    depends_on = set()
    tocheck = set()

    # src_dict ix the map from wire to the net (singular) where that wire
    # is a destination (i.e. it helps us find the wires used to make this wire)
    # i.e. assert src_dict[wire].dests[0] == wire
    src_dict, _ = block.net_connections()
    if wire in src_dict:
        tocheck.update(src_dict[wire].args)

    while tocheck:
        w = tocheck.pop()
        if w in depends_on:
            continue  # already checked, possible with diamond dependency

        depends_on.add(w)

        if isinstance(w, ModOutput) and not transitive:
            continue

        if (wire is not w) and isinstance(w, ModOutput):
            # If we're at a ModOutput and it's not the original wire we're checking
            # backward reachability for, then jump over the module and just get the
            # requires_set.
            for mod_input in w.sort.requires_set:
                tocheck.add(mod_input)

        elif not isinstance(w, (Input, Const, Register, MemBlock, RomBlock)):
            if w not in src_dict:
                if Verbose:
                    print(f"Warning: {w} not in src_dict")
            else:
                tocheck.update(set(src_dict[w].args))
    return depends_on
