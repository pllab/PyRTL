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

# [x]
class InputKind(abc.ABC):
    pass

# [x]
class Free(InputKind):
    def __init__(self, wire):
        self.wire = wire
        self.awaited_by_set = set()

    def __str__(self):
        return "Free"

# [x]
class Needed(InputKind):
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

# [x]
class OutputKind(abc.ABC):
    pass

# [x]
class Giving(OutputKind):
    def __init__(self, wire):
        self.wire = wire
        self.requires_set = set()

    def __str__(self):
        return "Giving"

# [x]
class Dependent(OutputKind):
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

def error_if_not_well_connected(to_wire, from_wire):
    # NOTE: this assumes everythings is in the same working block.

    from .module import ModInput, ModOutput
    assert isinstance(to_wire, ModInput)
    assert isinstance(to_wire.sort, (Free, Needed))
        
    if not isinstance(from_wire, ModOutput):
        # get all the ModOutputs that combinationally connect to this regular wire
        # TODO check this, it may getting all ModOutputs, not just the nearest
        from_output_wires = set(w for w in _backward_combinational_reachability(from_wire) if isinstance(w, ModOutput))
    else:
        from_output_wires = {from_wire}

    for from_wire in from_output_wires:
        assert isinstance(from_wire.sort, (Giving, Dependent))

        # from_wire is from module 1
        # to_wire is from module 2
        #
        # for each input wire w1 required by 'from_wire' (all of which are inputs to module 1):
        #   for each output wire w2 awaiting 'to_wire' (all of which are outputs of module 2):
        #       ensure w2 is **not** connected to w1
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
                    block = working_block() # TODO should be consistent about what block we're using
                    # dst_dict is map from a wire to the net(s) where that wire is a source
                    # TODO may be able to just call _modular_forward_reachability() form here....
                    _, dst_dict = block.net_connections()
                    if awaiting_wire in dst_dict:
                        # Actually need to follow the connections transitively,
                        # since PyRTL adds intermediate wires...
                        for net in dst_dict[awaiting_wire]:
                            # TODO we need to cross-over modules, but not enter them.
                            # i.e. if our net is dest is a module input, then continue
                            # with _that_ module's awaited_by_set, etc. until we can't
                            # go anymore (no non-stateful interceding elements) OR we hit
                            # out own from_wire again.
                            descendants = _modular_forward_reachability(net.dests[0], to_wire.module)
                            descendants.add(net.dests[0])
                            if required_wire in descendants:
                                raise PyrtlError(
                                    # TODO Include information about the lineage of wires causing this problem
                                    "Connection error!\n"
                                    f"{str(to_wire)} <<= {str(from_wire)}\n")
                    else:
                        # It's ambiguous, since we don't know for sure until the # entire circuit is connected.
                        # TODO improve this message, it's not very accurate/clear
                        if Verbose:
                            print(f"{awaiting_wire} of {awaiting_wire.module.name} is still disconnected, so the circuit is still ambiguous")


# [x]
def annotate_module(module):
    for wire in module.inputs().union(module.outputs()):
        wire.sort = get_wire_sort(wire, module)

# [x]
def get_wire_sort(wire, module):
    from .module import ModInput, ModOutput

    if isinstance(wire, ModInput):
        # Get its forward reachability (wires that 'wire' combinationally affects)...
        forward = _forward_combinational_reachability(wire, module.block)
        # ... and then just filter for the module outputs that wire affects
        affects = set(w for w in forward if w in module.outputs())
        if affects:
            return Needed(wire, affects)
        return Free(wire)
    elif isinstance(wire, ModOutput):
        # Get its backward reachbility (wires that 'wire' combinationally depends on)...
        backward = _backward_combinational_reachability(wire, module.block)
        # ... and then jus tilfter for the module inputs it depends on
        depends = set(w for w in backward if w in module.inputs())
        if depends:
            return Dependent(wire, depends)
        return Giving(wire)
    else:
        raise PyrtlError("Only get wire sorts of inputs/outputs")

# This function and _modular_affects_iter are used for jumping over
# modules by, given an input, getting their affected outputs via their
# sorts. This way we don't descend into the module logic itself
# (theoretically saving a lot of time not having to navigate that module's
# netlist again), instead taking advantage of the whole "awaited-by"/"requires" set that each module computes once on its own.
# Note: this needs to be computed each time because of updates to the entire circuit
# (though we could probably cache the previous results and only check for updates...)
def _modular_forward_reachability(wire, module) -> Set[WireVector]:
    # Really, returns just ModInputs, at least that's the hope
    from .module import ModInput
    _, dest_dict = module.block.net_connections()
    to_check = {wire}
    affects_inputs = set()

    while to_check:
        w = to_check.pop()
        affected_mod_inputs = set(w for w in _modular_affects_iter(w, dest_dict) if isinstance(w, ModInput))
        for mod_input in affected_mod_inputs:
            for awaiting_output_wire in mod_input.sort.awaited_by_set:
                to_check.add(awaiting_output_wire)
                # Reason you want to search again is because these wires may be connected to
                # other modules via intermediate wires
            affects_inputs.add(mod_input)
    return affects_inputs


def _modular_affects_iter(wire, dest_dict):
    from .module import ModInput
    if isinstance(wire, (ModInput, Const, Register, MemBlock, RomBlock, Input, Output)):
        return {wire}

    affects = set()
    tocheck = set()

    if wire not in dest_dict:
        return {wire}

    for net in dest_dict[wire]:
        # Sanity checks!
        # assert wire in net.args # I *would* do this, but PyRTL complains about using boolean comparison on wires, *sigh*
        # assert len(net.dests) == 1 # FYI: The *one* time when len(net.dests) is not 1 is when the net logic op is '@' (write data to mem)
        if net.dests:
            tocheck.add(net.dests[0])

    while tocheck:
        w = tocheck.pop()
        if w in affects:
            continue  # already checked, possible with diamond dependency
        if not isinstance(w, (ModInput, Input, Output, Const, Register, MemBlock, RomBlock)):
            if w not in dest_dict:
                if Verbose:
                    print(f"Warning: {w} not in dest_dict")
            else:
                for net in dest_dict[w]:
                    # assert w in net.args # I *would* do this, but PyRTL complains about using boolean comparison on wires, *sigh*
                    # assert len(net.dests) == 1 # FYI: The *one* time when len(net.dests) is not 1 is when the net logic op is '@' (write data to mem)
                    if net.dests:
                        tocheck.add(net.dests[0])
        affects.add(w)
    return affects

# [x]
def _forward_combinational_reachability(wire, block=None) -> Set[WireVector]:
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

        if (wire is not w) and isinstance(w, ModInput):
            # If we're at a ModOutput and it's not the original wire we're checking
            # backward reachability for, then jump over the module and just get the
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
        affects.add(w)
    return affects

# [x]
def _backward_combinational_reachability(wire, block=None):
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
        depends_on.add(w)
    return depends_on
