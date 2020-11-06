# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

import abc

from .pyrtlexceptions import PyrtlError
from .core import working_block
from .wire import Register

class InputSort(abc.ABC):
    pass

class Free(InputSort):
    # Allowing wire=None allows these to be used instantiated as ascriptions
    def __init__(self, wire=None):
        self.wire = wire
        self.needed_by_set = set()

    def __str__(self):
        return "Free"

class Needed(InputSort):
    def __init__(self, needed_by_set, wire=None, ascription=True):
        from .module import _ModOutput
        self.wire = wire
        self.needed_by_set = needed_by_set
        self.ascription = ascription
        # Sanity check
        if not self.ascription:
            for w in self.needed_by_set:
                assert(isinstance(w, _ModOutput))


    def __str__(self):
        wns = ", ".join(map(str, sorted(self.needed_by_set, key=lambda w: w._original_name)))
        return f"Needed (needed by: {wns})"

class OutputSort(abc.ABC):
    pass

class Giving(OutputSort):
    def __init__(self, wire=None):
        self.wire = wire
        self.depends_on_set = set()

    def __str__(self):
        return "Giving"

class Dependent(OutputSort):
    def __init__(self, depends_on_set, wire=None, ascription=True):
        from .module import _ModInput
        self.wire = wire
        self.depends_on_set = depends_on_set
        self.ascription = ascription
        # Sanity check
        if not self.ascription:
            for w in self.depends_on_set:
                assert(isinstance(w, _ModInput))

    def __str__(self):
        wns = ", ".join(map(str, sorted(self.depends_on_set, key=lambda w:w._original_name)))
        return f"Dependent (depends on: {wns})"


Verbose = False

# TODO a function that just checks if a new connection introduces a problem, without
# us having to do all the extra checks if possible
# was "error_if_not_well_connected"

def is_well_connected_block(block=None):
    """ Check if all modules in a block are well-connected to one another.

        Compute the intermodular reachability once to save some computation hopefully. 
    """
    block = working_block(block)
    wires_to_inputs = _build_intermodular_reachability_maps(block.modules)
    return all(is_well_connected_module(m, wires_to_inputs) for m in block.modules)

def is_well_connected_module(module, wires_to_inputs):
    """ Check if a single module is well-connected """
    # TODO need to make sure I can do this when the circuit is not yet complete,
    # and be adding to it as you go/add wirevectors to the block

    from .module import _ModInput, _ModOutput

    for output in module.outputs:
        for input in wires_to_inputs[output]:
            if isinstance(output.sort, Dependent) and isinstance(input.sort, Needed):
                for depends_on_w in output.sort.depends_on_set:
                    assert isinstance(depends_on_w, _ModInput)
                    for needed_by_w in input.sort.needed_by_set:
                        assert isinstance(needed_by_w, _ModOutput)
                        if depends_on_w in wires_to_inputs[needed_by_w]:
                            print(f"ill-connection between {str(input)} ({input.module.name}) and {str(output)} ({output.module.name})")
                            return False
    return True

def _build_intermodular_reachability_maps(modules):
    """ Right now, just computes for each module output and wire outside a module, the set of module inputs it reaches combinationally """
    from .module import _ModOutput

    # map from wire to set of module inputs it forward affects, combinationally
    wires_to_inputs = {}

    block = list(modules)[0].block
    src_map, _ = block.net_connections()

    for module in modules:
        for input in module.inputs:
            work_list = [input]
            seen = set()

            while work_list:
                s = work_list.pop()
                if s in seen:
                    continue
                seen.add(s)

                if s is not input:
                    if s not in wires_to_inputs:
                        wires_to_inputs[s] = {input}
                    else:
                        wires_to_inputs[s].add(input)
                
                # Must take advantage of module annotations so we
                # don't need to descend into more nets than needed
                if isinstance(s, _ModOutput):
                    work_list.extend(s.sort.depends_on_set)
                else:
                    # Registers break the combinational chain
                    if isinstance(s, Register):
                        continue

                    if s not in src_map:
                        continue
                    src_net = src_map[s]
                    assert src_net.dests[0] is s

                    if src_net.op == 'm' and src_net.op_params[1].asynchronous == False:
                        continue
                    if src_net.op == '@':
                        continue
                    work_list.extend(src_net.args)

    # Add empty sets for at least the output wires that never reached an some other module's input combinationally
    for o in module.outputs:
        if o not in wires_to_inputs:
            wires_to_inputs[o] = set()

    return wires_to_inputs

def _build_intramodular_reachability_maps(module):
    """ Constructs the awaited_by/depends_on maps limited to the module given.

        Assumes that modules are well-constructed in that all internal wires are
        really internal (i.e. not connected to wires defined outside the module). 

        The advantage of this is that annotating each module input/output
        only requires traversing the module once at the beginning to build these maps,
        rather than for each io.
    """
    from .module import _ModInput, _ModOutput

    # map from wire to the outputs it affects, combinationally
    needed_by = {}
    # map from wire to the inputs it depends on, combinationally
    depends_on = {}

    block = module.block
    src_map, dst_map = block.net_connections()

    for output in module.outputs:
        # print(f"Output {str(output)}")
        work_list = [output]
        seen = set()

        while work_list:
            a = work_list.pop()
            if a in seen:
                continue
            seen.add(a)
            # print(f"checking {str(a)}")

            if module and hasattr(a, 'module'):
                assert a.module == module

            # Registers break the combinational chain
            if isinstance(a, Register):
                continue

            if a is not output:
                if a not in needed_by:
                    needed_by[a] = {output}
                else:
                    needed_by[a].add(output)
            if a not in src_map:
                continue
            src_net = src_map[a]
            assert src_net.dests[0] is a

            if src_net.op == 'm' and src_net.op_param[1].asynchronous == False:
                continue
            if src_net.op == '@':
                raise PyrtlError("memwrites should not have a destination wire")
            if isinstance(a, _ModInput):
                # Enforces that we stay within the module
                continue

            work_list.extend(src_net.args)

    for input in module.inputs:
        # print(f"Input {str(input)}")
        work_list = [input]
        seen = set()

        while work_list:
            d = work_list.pop()
            if d in seen:
                continue
            seen.add(d)
            # print(f"checking {str(d)}")

            if module and hasattr(d, 'module'):
                assert d.module == module

            if d is not input:
                if d not in depends_on:
                    depends_on[d] = {input}
                else:
                    depends_on[d].add(input)
            if d not in dst_map:
                continue
            dst_nets = dst_map[d]

            # Registers break the combinational chain
            if isinstance(d, Register):
                continue
            if isinstance(d, _ModOutput):
                # Enforces that we stay within the module
                continue

            for dst_net in dst_nets:
                assert any({d is arg for arg in dst_net.args})
                if dst_net.op == 'm' and dst_net.op_params[1].asynchronous == False:
                    continue
                if dst_net.op == '@':
                    continue
                work_list.append(dst_net.dests[0])
    
    # Add empty sets for at least the input/output wires that were never reached combinationally
    for io in module.inputs.union(module.outputs):
        if io not in needed_by:
            needed_by[io] = set()
        if io not in depends_on:
            depends_on[io] = set()
    
    return needed_by, depends_on

def sort_matches(ascription, sort):
    # User can just supply classname (e.g. sort=Needed) without specifying _what_
    # the wire needs; that's fine, we just won't compare against the wires it needs.
    if isinstance(ascription, type) and isinstance(sort, ascription):
        return True

    # Otherwise user supplied an instance of the InputSort/OutputSort class:
    if isinstance(ascription, Free) and isinstance(sort, Free):
        return True
    if isinstance(ascription, Giving) and isinstance(sort, Giving):
        return True
    if isinstance(ascription, Needed) and isinstance(sort, Needed):
        expected_names = ascription.needed_by_set
        actual_names = set({w._original_name for w in sort.needed_by_set})
        return expected_names == actual_names
    if isinstance(ascription, Dependent) and isinstance(sort, Dependent):
        expected_names = ascription.depends_on_set
        actual_names = set({w._original_name for w in sort.depends_on_set})
        return expected_names == actual_names

    return False

def annotate_module(module):
    if Verbose:
        print(f"Annotating module {module.name} with "
              f"{len(module.inputs)} inputs and {len(module.outputs)} outputs")

    needed_by, depends_on = _build_intramodular_reachability_maps(module=module)

    for io in module.inputs.union(module.outputs):
        sort = get_wire_sort(io, needed_by, depends_on)

        # If wire.sort was ascribed, check it and report if not matching.
        # The user can provide the classname of the sort or an actual instance of the class.
        if io.sort and not sort_matches(io.sort, sort):
            raise PyrtlError(
                f"Unmatched sort ascription on wire {str(io)} in module {io.module.name}.\n"
                f"User provided {io.sort.__name__}\n"
                f"But we computed {str(sort)}")
        io.sort = sort

def get_wire_sort(wire, needed_by, depends_on):
    from .module import _ModInput, _ModOutput

    if isinstance(wire, _ModInput):
        input = wire
        ab = needed_by[input]
        if ab:
            return Needed(ab, wire=input, ascription=False)
        else:
            return Free(input)
    elif isinstance(wire, _ModOutput):
        output = wire
        do = depends_on[output]
        if do:
            return Dependent(do, wire=output, ascription=False)
        else:
            return Giving(output)