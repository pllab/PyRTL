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

class InputKind(abc.ABC):
    pass

class Free(InputKind):
    def __init__(self, wire):
        self.wire = wire
        self.awaited_by_set = set()

    def __str__(self):
        return "Free"

class Needed(InputKind):
    def __init__(self, wire, awaited_by_set):
        self.wire = wire
        self.awaited_by_set = awaited_by_set

    def __str__(self):
        wns = ", ".join(map(str, self.awaited_by_set))
        return f"Needed (needed by: {wns})"

class OutputKind(abc.ABC):
    pass

class Giving(OutputKind):
    def __init__(self, wire):
        self.wire = wire
        self.requires_set = set()

    def __str__(self):
        return "Giving"

class Dependent(OutputKind):
    def __init__(self, wire, requires_set):
        self.wire = wire
        self.requires_set = requires_set

    def __str__(self):
        wns = ", ".join(map(str, self.requires_set))
        return f"Dependent (depends on: {wns})"

def error_if_not_well_connected(to_wire, from_wire):
    from .module import ModInput, ModOutput
    assert isinstance(to_wire, ModInput)
    assert isinstance(from_wire, ModOutput)
    assert isinstance(to_wire.sort, (Free, Needed))
    assert isinstance(from_wire.sort, (Giving, Dependent))
    assert to_wire.module.block == from_wire.module.block

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
                _, dst_dict = block.net_connections()
                if awaiting_wire in dst_dict:
                    # Actually need to follow the connections transitively,
                    # since PyRTL adds intermediate wires...
                    for net in dst_dict[awaiting_wire]:
                        # TODO need to NOT cross-over into intra-modular boundaries;
                        # we should just stop tracing descendants once we reach a module input/output
                        descendants = _forward_reachability(net.dests[0], to_wire.module.block)
                        descendants.add(net.dests[0])
                        if required_wire in descendants:
                            raise PyrtlError(
                                # TODO Include information about the lineage of wires causing this problem
                                "Connection error!\n"
                                f"{str(to_wire)} <<= {str(from_wire)}\n")
                else:
                    # It's ambiguous, since we don't know for sure until the # entire circuit is connected.
                    # TODO improve this message, it's not very accurate/clear
                    # TODO run this with 'TestDifferentSizes' unit test, not sure if this warning is correct
                    print(f"{awaiting_wire} is still disconnected, so the circuit is still ambiguous")


def annotate_module(module):
    for wire in module.inputs().union(module.outputs()):
        wire.sort = get_wire_sort(wire, module)

def get_wire_sort(wire, module):
    from .module import ModInput, ModOutput

    if isinstance(wire, ModInput):
        # Get its forward reachability
        forward = _forward_reachability(wire, module.block)
        affects = set(w for w in forward if w in module.outputs())
        if affects:
            return Needed(wire, affects)
        return Free(wire)
    elif isinstance(wire, ModOutput):
        # Get its backward reachbility
        backward = _backward_reachability(wire, module.block)
        depends = set(w for w in backward if w in module.inputs())
        if depends:
            return Dependent(wire, depends)
        return Giving(wire)
    else:
        raise Exception("Only get wire sorts of inputs/outputs")

def _forward_reachability(wire, block) -> Set[WireVector]:
    """ Get the module outputs that wire combinationally affects """
    _, dest_dict = block.net_connections()
    return _affects_iter(wire, dest_dict)

def _affects_iter(wire, dest_dict):
    """
        :param wire: input wire whose combinationally-reachable descendant wires we want to find
        :param dest_dict: the map from wire to the nets (plural) where that wire
                         is a source (i.e. it helps us find the wires that this wire affects)
                         i.e.
                            for net in dest_dict[wire]:
                                assert wire in net.args
        Handles if there are combinational loops
    """
    from .module import ModOutput
    # TODO I'm really wondering if having ModOutput here will affect the correctness
    # of computing 'error_if_not_well_connected'? (like what if it stops early because of this...)
    if isinstance(wire, (ModOutput, Const, Register, MemBlock, RomBlock, Output)):
        return {wire}

    # wire is Input or normal wire
    affects = set()
    tocheck = set()

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
        if not isinstance(w, (ModOutput, Output, Const, Register, MemBlock, RomBlock)):
            if w not in dest_dict:
                print(f"Warning: {w} not in dest_dict")
            else:
                for net in dest_dict[w]:
                    # assert w in net.args # I *would* do this, but PyRTL complains about using boolean comparison on wires, *sigh*
                    # assert len(net.dests) == 1 # FYI: The *one* time when len(net.dests) is not 1 is when the net logic op is '@' (write data to mem)
                    if net.dests:
                        tocheck.add(net.dests[0])
        affects.add(w)
    return affects

def _backward_reachability(wire, block):
    """ Get the module inputs that wire combinationally depends on """
    src_dict, _ = block.net_connections()
    return _depends_on_iter(wire, src_dict)

def _depends_on_iter(wire, src_dict):
    """
        :param wire: output wire whose combinationally-reachable ancestor wires we want to find
        :param src_dict: the map from wire to the net (singular) where that wire
                         is a destination (i.e. it helps us find the wires used to make this wire)
                         i.e. assert src_dict[wire].dests[0] == wire

        Handles if there are combinational loops
    """
    from .module import ModInput
    if isinstance(wire, (ModInput, Const, Register, MemBlock, RomBlock, Input)):
        return {wire}

    # wire is Output or normal wire
    depends_on = set()
    tocheck = set()

    # Sanity check!
    # assert src_dict[wire].dests[0] == wire  # Can't do this because it elaborates to an = operator, don't want that

    tocheck.update(set(src_dict[wire].args))
    while tocheck:
        w = tocheck.pop()
        if w in depends_on:
            continue  # already checked, possible with diamond dependency
        if not isinstance(w, (ModInput, Input, Const, Register, MemBlock, RomBlock)):
            if w not in src_dict:
                # Occurs when there are no Input wires that a module input is tied to currently.
                # Main reason: we don't have a module type nor a module input wire type
                print(f"Warning: {w} not in src_dict")
            else:
                tocheck.update(set(src_dict[w].args))
        depends_on.add(w)
    return depends_on
