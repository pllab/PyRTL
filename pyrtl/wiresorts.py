"""
Set of classes and functions for expressing the "sort" of a wire.
Here we're currently concerned with defining intermodular dependencies
via the Free, Needed, Giving, and Dependent wire sorts, and using these
sorts for determining well-connectedness.
"""

from .pyrtlexceptions import PyrtlError, PyrtlInternalError
from .core import working_block
from .wire import Register

Verbose = False


def _verbose_print(s):
    if Verbose:
        print(s)

class InputSort(object):
    """ Base class for the sorts that can be assigned to module inputs """
    pass


class Free(InputSort):
    """ The wire sort for module inputs that are not combinationally connected
        to any its module's outputs """

    def __init__(self, ascription=True):
        self.needed_by_set = set()
        self.ascription = ascription

    def __str__(self):
        return "Free"


class Needed(InputSort):
    """ The wire sort for module inputs that *are* combinationally connected
        to one or more of its module's outputs """

    def __init__(self, needed_by_set, ascription=True):
        from .module import _ModOutput
        self.needed_by_set = needed_by_set
        self.ascription = ascription
        # Sanity check
        if not self.ascription:
            for w in self.needed_by_set:
                assert(isinstance(w, _ModOutput))

    def __str__(self):
        wns = ", ".join(map(str, sorted(self.needed_by_set, key=lambda w: w._original_name)))
        return "Needed (needed by: %s)" % wns


class OutputSort(object):
    """ Base class for the sorts that can be assigned to module outputs """
    pass


class Giving(OutputSort):
    """ A wire sort for module outputs that are not combinationally connected
        to any its module's inputs """

    def __init__(self, ascription=True):
        self.depends_on_set = set()
        self.ascription = ascription

    def __str__(self):
        return "Giving"


class Dependent(OutputSort):
    """ The wire sort for module outputs that *are* combinationally connected
        to one or more of its module's inputs """

    def __init__(self, depends_on_set, ascription=True):
        from .module import _ModInput
        self.depends_on_set = depends_on_set
        self.ascription = ascription
        # Sanity check
        if not self.ascription:
            for w in self.depends_on_set:
                assert(isinstance(w, _ModInput))

    def __str__(self):
        wns = ", ".join(map(str, sorted(self.depends_on_set, key=lambda w: w._original_name)))
        return "Dependent (depends on: %s)" % wns

def sanity_check_input_sort(sort, wirename):
    if (sort
            and (sort not in (Free, Needed))
            and (not isinstance(sort, (Free, Needed)))):
        raise PyrtlError(
            'Invalid sort ascription for input "%s" '
            '(must provide either Free or Needed type name or instance).'
            % wirename
        )

def sanity_check_output_sort(sort, wirename):
    if (sort
            and (sort not in (Giving, Dependent))
            and (not isinstance(sort, (Giving, Dependent)))):
        raise PyrtlError(
            'Invalid sort ascription for output "%s" '
            '(must provide either Giving or Dependent type name or instance).'
            % wirename
        )

def check_module_interconnections(supermodule=None):
    """ Check if all modules in a supermodule (or the block if not given)
        are well-connected to one another.

        Compute the intermodular reachability once to save some computation hopefully.
        If there is more than one bad connection between a pair of modules, we report
        all of them.

        TODO We should probably *not* report all the module interconnections that are a part
        of the same logical loop, however. Just one in the loop suffices.
    """
    if not supermodule:
        modules = working_block().toplevel_modules
    else:
        modules = supermodule.submodules

    if not modules:
        return

    bad_connections = []
    wires_to_inputs = _build_intermodular_reachability_maps(modules)
    for m in modules:
        bad_conn = find_bad_connection_from_module(m, wires_to_inputs)
        if bad_conn:
            bad_connections.append(bad_conn)

    if bad_connections:
        raise PyrtlError(
            'Invalid intermodular connections detected in "%s":\n%s'
            % (supermodule.name if supermodule else "Top",
               "\n".join("(%s -> %s)" % (str(output), str(input))
                         for (output, input) in bad_connections))
        )


def find_bad_connection_from_module(module, wires_to_inputs=None):
    """ Check if a single module is well-connected to other modules in the block.
        Returns the first bad connection found originating from it.
    """

    from .module import _ModInput, _ModOutput

    if not wires_to_inputs:
        wires_to_inputs = _build_intermodular_reachability_maps([module])

    for output in module.outputs:
        for input in wires_to_inputs[output]:
            if not output.sort:
                raise PyrtlInternalError(
                    'Cannot check well-connectedness of output wire "%s" that '
                    'hasn\'t been annotated.' % str(output)
                )
            if not input.sort:
                raise PyrtlInternalError(
                    'Cannot check well-connectedness of input wire "%s" that '
                    'hasn\'t been annotated.' % str(input)
                )
            # Note that ascriptions are fine, because by this point they should have
            # been validated as correct, or thrown an error otherwise
            if isinstance(output.sort, Dependent) and isinstance(input.sort, Needed):
                for depends_on_w in output.sort.depends_on_set:
                    assert isinstance(depends_on_w, _ModInput)
                    for needed_by_w in input.sort.needed_by_set:
                        assert isinstance(needed_by_w, _ModOutput)
                        if depends_on_w in wires_to_inputs[needed_by_w]:
                            return (output, input)
    return None


def _build_intermodular_reachability_maps(modules):
    """ Right now, just computes for each module output and wire outside a module,
        the set of module inputs it reaches combinationally
    """
    from .module import _ModOutput

    # map from wire to set of module inputs it forward affects, combinationally
    wires_to_inputs = {}

    block = list(modules)[0].block
    src_map, _ = block.net_connections()

    for module in modules:

        for o in module.outputs:
            wires_to_inputs[o] = set()

        for input in module.inputs:
            work_list = [input]
            seen = set()

            while work_list:
                s = work_list.pop()
                if s in seen:
                    continue
                seen.add(s)

                if s is not input:
                    wires_to_inputs.setdefault(s, set()).add(input)

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

                    if src_net.op == 'm' and not src_net.op_param[1].asynchronous:
                        continue
                    if src_net.op == '@':
                        continue
                    work_list.extend(src_net.args)

    # Just return the outputs
    wires_to_inputs = {o: s for o, s in wires_to_inputs.items() if isinstance(o, _ModOutput)}
    return wires_to_inputs


def _build_intramodular_reachability_maps(module):
    """ Constructs the awaited_by/depends_on maps limited to the module given.

        Assumes that modules are well-constructed in that all internal wires are
        really internal (i.e. not connected to wires defined outside the module).

        The advantage of this is that annotating each module input/output
        only requires traversing the module once at the beginning to build these maps,
        rather than for each io.

        The intention of this is purely for intramodular dependency calculation;
        checks for valid intermodular connections is done in is_well_connected_module
        (which uses the _build_intermodular_reachability_maps).
    """
    from .module import _ModInput, _ModOutput

    # map from any wire to the outputs it affects, combinationally;
    # we track every wire's affected output for effiency during
    # traversal, but by the end we'll just return a map whose keys are just *input*,
    # so let's make sure the inputs are at least present right now
    needed_by = {i: set() for i in module.inputs}

    # map from *output* to the inputs it depends on, combinationally;
    # this is calculated using needed_by for efficiency.
    depends_on = {o: set() for o in module.outputs}

    block = module.block
    src_map, _ = block.net_connections()

    for output in module.outputs:
        _verbose_print("Output " + str(output))
        work_list = [output]
        seen = set()

        while work_list:
            a = work_list.pop()
            if a in seen:
                continue
            seen.add(a)
            _verbose_print("checking " + str(a))

            # Registers break the combinational chain
            if isinstance(a, Register):
                continue

            if a.module != output.module:
                # Skip over the submodule by going backwards to its inputs
                if not isinstance(a, _ModOutput):
                    raise PyrtlInternalError(
                        'The sanity checks should have detected this invalid '
                        'connection originating from "%s.%s" in module "%s" by now.'
                        % (a.module.name, a.name, output.module.name)
                    )
                if not a.sort:
                    raise PyrtlInternalError(
                        'All submodules should be annotated before attempting to '
                        'annotate their supermodule. Here, submodule "%s" in "%s" '
                        'is not yet annotated.' % (a.module.name, output.module.name)
                    )
                assert isinstance(a.sort, OutputSort)
                for affector in a.sort.depends_on_set:
                    if affector in src_map:
                        work_list.extend(src_map[affector].args)
            else:
                if a is not output:  # For simplicity, we added the initial output to the work list
                    needed_by.setdefault(a, set()).add(output)
                if a not in src_map:
                    continue
                src_net = src_map[a]
                assert src_net.dests[0] is a

                if src_net.op == 'm' and not src_net.op_param[1].asynchronous:
                    continue
                if src_net.op == '@':
                    raise PyrtlError("memwrites should not have a destination wire")
                if isinstance(a, _ModInput):  # Stay within the module
                    continue

                work_list.extend(src_net.args)

    # Just care about needed_by set of the inputs
    needed_by = {i: s for i, s in needed_by.items() if i in module.inputs}

    # Now create the depends_on map, which is essentially the inverse
    for input in module.inputs:
        for output in needed_by[input]:
            assert isinstance(output, _ModOutput) and output.module == input.module
            depends_on[output].add(input)

    return needed_by, depends_on


def sort_matches(ascription, sort):
    # if isinstance(ascription, type):
    #     # There is actually a subsort relation that has formed:
    #     #
    #     # A free input wire can be labelled as needed
    #     # A giving output wire can be labelled as dependent
    #     #
    #     # Doing either is a way of forcing an attached output ('needed' input case) to be giving,
    #     # but in these cases, there won't be any valid members of the needed-by-set.
    #     # Right now, only allow them to do such a thing via supplying the classname, rather
    #     # than an instance of the class (which will have internal sets to compare). So support
    #     # for this is experimental right now.
    #     # F <: N
    #     if ascription is Free:
    #         return isinstance(sort, Free)
    #     if ascription is Needed:
    #         return isinstance(sort, (Free, Needed))
    #     # G <: D
    #     if ascription is Giving:
    #         return isinstance(sort, Giving)
    #     if ascription is Dependent:
    #         return isinstance(sort, (Giving, Dependent))

    # User can just supply classname (e.g. sort=Needed) without specifying _what_
    # the wire needs; that's fine, we just won't compare against the wires it needs.
    if isinstance(ascription, type):
        return isinstance(sort, ascription)

    # Otherwise user supplied an instance of the InputSort/OutputSort class:
    assert ascription.ascription
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
    _verbose_print("Annotating module %s{module.name} with %d inputs and %d outputs."
                   % (module.name, len(module.inputs), len(module.outputs)))
    modname = module.__class__.__name__

    # For efficiency, only calculate the wire sorts of a module once;
    # save the information in the block
    if modname in module.block.module_sorts:
        _verbose_print("Using cached sort information for %s" % modname)
        sorts = module.block.module_sorts[modname]
        for io in module.inputs.union(module.outputs):
            # Now make sure our particular instance of this module refers
            # to our own ModInputs/ModOutputs
            def update_set(s):
                r = set()
                for w in s:
                    r.add(getattr(module, w._original_name))
                return r

            sort = sorts[io._original_name]
            if isinstance(sort, Free):
                io.sort = Free(ascription=False)
            elif isinstance(sort, Giving):
                io.sort = Giving(ascription=False)
            elif isinstance(sort, Needed):
                io.sort = Needed(update_set(sort.needed_by_set), ascription=False)
            else:
                io.sort = Dependent(update_set(sort.depends_on_set), ascription=False)
    else:
        sortmap = {}
        needed_by, depends_on = _build_intramodular_reachability_maps(module=module)

        for io in module.inputs.union(module.outputs):
            sort = _make_wire_sort(io, needed_by, depends_on)

            # If wire.sort was ascribed, check it and report if not matching.
            # The user can provide the classname of the sort or an actual instance of the class.
            if io.sort and not sort_matches(io.sort, sort):
                raise PyrtlError(
                    "Unmatched sort ascription on wire %s.\n"
                    "User provided %s.\n"
                    "But we computed %s."
                    % (str(io), io.sort.__name__, str(sort)))
            io.sort = sort

            sortmap[io._original_name] = sort

        module.block.module_sorts[modname] = sortmap


def _make_wire_sort(wire, needed_by, depends_on):
    from .module import _ModInput, _ModOutput

    if isinstance(wire, _ModInput):
        input = wire
        nb_set = needed_by[input]
        if nb_set:
            return Needed(nb_set, ascription=False)
        else:
            return Free(input)
    elif isinstance(wire, _ModOutput):
        output = wire
        do_set = depends_on[output]
        if do_set:
            return Dependent(do_set, ascription=False)
        else:
            return Giving(output)
