# pylint: disable=no-member

import unittest
import six

import pyrtl


class OneBitAdder(pyrtl.Module):
    def __init__(self, name=""):
        super(OneBitAdder, self).__init__(name=name)

    def definition(self):
        a = self.Input(1, 'a')
        b = self.Input(1, 'b')
        cin = self.Input(1, 'cin')
        s = self.Output(1, 's')
        cout = self.Output(1, 'cout')
        s <<= a ^ b ^ cin
        cout <<= (a & b) | (a & cin) | (b & cin)


class NBitAdder(pyrtl.Module):
    def __init__(self, n, name=""):
        assert (n > 0)
        self.n = n
        super(NBitAdder, self).__init__(name=name)

    def definition(self):
        a = self.Input(self.n, 'a')
        b = self.Input(self.n, 'b')
        cin = self.Input(1, 'cin')
        cout = self.Output(1, 'cout')
        s = self.Output(self.n, 's')

        ss = []
        for i in range(self.n):
            oba = OneBitAdder(name="oba_" + str(i))
            oba.a <<= a[i]
            oba.b <<= b[i]
            oba.cin <<= cin
            ss.append(oba.s)
            cin = oba.cout
        s <<= pyrtl.concat_list(ss)
        cout <<= cin


class TestBlockAttributes(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_no_modules_instantiated(self):
        self.assertEqual(pyrtl.working_block().modules, set())
        self.assertEqual(pyrtl.working_block().toplevel_modules, set())
        self.assertEqual(pyrtl.working_block().modules_by_name, {})

    def test_no_current_module(self):
        self.assertIsNone(pyrtl.working_block().current_module)

    def test_several_modules_instantiated(self):
        tester = self

        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__()

            def definition(self):
                a = self.Input(3, name='a')
                b = self.Output(3, name='b')
                b <<= a
                tester.assertEqual(self.block.current_module, self)

        m1 = M()
        m2 = M()
        for module in pyrtl.working_block().modules:
            self.assertTrue(module.name.startswith('mod_'))
        self.assertEqual(set(pyrtl.working_block().modules), {m1, m2})

    def test_several_named_modules_instantiated(self):
        tester = self

        class A(pyrtl.Module):
            def __init__(self, name):
                super(A, self).__init__(name)

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a
                tester.assertEqual(self.block.current_module, self)

        a1 = A('a1')
        a2 = A('a2')
        self.assertEqual(pyrtl.working_block().modules_by_name['a1'], a1)
        self.assertEqual(pyrtl.working_block().modules_by_name['a2'], a2)

    def test_duplicate_module_names(self):
        class M(pyrtl.Module):
            def __init__(self, name):
                super(M, self).__init__(name=name)

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a
        M('m1')

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M('m1')
        self.assertEqual(
            str(ex.exception),
            'Module with name "m1" already exists.'
        )


class TestBadModule(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_no_definition(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertEqual(
            str(ex.exception),
            'Module subclasses must supply a `definition` method'
        )

    def test_bad_mod_name(self):
        class M(pyrtl.Module):
            def __init__(self, name):
                super(M, self).__init__(name=name)

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M("mod_1")
        self.assertEqual(
            str(ex.exception),
            'Starting a module name with "mod_" is reserved for internal use.'
        )

    def test_no_output(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__()

            def definition(self):
                _ = pyrtl.Const(4)

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertEqual(
            str(ex.exception),
            "Module must have at least one output."
        )

    def test_empty_io_name(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__()

            def definition(self):
                a = self.Input(3, name='')
                b = self.Output(3, name='b')
                b <<= a

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertEqual(
            str(ex.exception),
            "Must supply a non-empty name for a module's input/output wire"
        )

    def test_duplicate_io_names(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__()

            def definition(self):
                a = self.Input(3, name='a')
                b = self.Output(3, name='a')
                c = self.Output(4, name='c')
                d = self.Output(4, name='d')
                e = self.Output(1, name='d')
                b <<= a
                c <<= a + 1
                d <<= a - 1
                e <<= 0

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertEqual(
            str(ex.exception),
            "Duplicate names found for the following different module "
            "input/output wires: ['a', 'd'] (make sure you are not using \"mod_\" "
            "as a prefix because that is reserved for internal use)."
        )

    def test_nonexistent_io_access(self):
        class A(pyrtl.Module):
            def __init__(self, name):
                super(A, self).__init__(name=name)

            def definition(self):
                o = self.Output(4, 'o')
                o <<= 4
        a = A('m1')
        with self.assertRaises(AttributeError) as ex:
            a.x
        self.assertEqual(
            str(ex.exception),
            'Cannot get non-IO wirevector/submodule "x" from module "m1".\n'
            'Make sure you spelled the wire name correctly, '
            'that you used "self.Input" and "self.Output" rather than '
            '"pyrtl.Input" and "pyrtl.Output" to declare the IO wirevectors, '
            'and that you are accessing it from the correct module.\n'
            'Available input wires are [] and output wires are [\'o/4O[m1]\'].\n'
            'Available submodules are [].'
        )

    def test_unconnected_inputs(self):
        class A(pyrtl.Module):
            def __init__(self, name):
                super(A, self).__init__(name=name)

            def definition(self):
                i = self.Input(4, 'i')
                o = self.Output(4, 'o')
                o <<= 4
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            A('m1')
        self.assertEqual(
            str(ex.exception),
            'Invalid module. Input "i/4I[m1]" is not connected '
            'to any internal module logic.'
        )

    def test_unconnected_outputs(self):
        class A(pyrtl.Module):
            def __init__(self, name):
                super(A, self).__init__(name=name)

            def definition(self):
                _o = self.Output(4, 'o')
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            A('m1')
        self.assertEqual(
            str(ex.exception),
            'Invalid module. Output "o/4O[m1]" is not connected '
            'to any internal module logic.'
        )

    def test_no_super_call_in_initializer(self):
        class M(pyrtl.Module):
            def __init__(self):
                pass

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(3, 'o')
                o <<= i + 1

        with self.assertRaises(KeyError) as ex:
            m = M()
            print(m.i.name)
        self.assertEqual(str(ex.exception), "'inputs_by_name'")

    def test_bad_input_as_dest(self):
        class M(pyrtl.Module):
            def __init__(self, name):
                super(M, self).__init__(name=name)

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                i <<= 3
                o <<= i

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M('m1')
        self.assertTrue(str(ex.exception).startswith('Invalid connection'))


class TestSimpleModule(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = OneBitAdder()

    def test_internal_names(self):
        self.assertTrue

    def test_inputs(self):
        self.assertEqual(self.module.inputs, {self.module.a, self.module.b, self.module.cin})

    def test_outputs(self):
        self.assertEqual(self.module.outputs, {self.module.s, self.module.cout})

    def test_to_block_io(self):
        block = self.module.block
        self.assertEqual(block.wirevector_subset((pyrtl.Input, pyrtl.Output)), set())
        self.module.to_block_io()
        for w in self.module.inputs:
            wio = block.get_wirevector_by_name(w._original_name)
            self.assertTrue(isinstance(wio, pyrtl.Input))
        for w in self.module.outputs:
            wio = block.get_wirevector_by_name(w._original_name)
            self.assertTrue(isinstance(wio, pyrtl.Output))

    def test_wires_have_module_attribute(self):
        for wire in self.module.wires:
            self.assertTrue(wire.module == self.module)

    def test_correctness(self):
        a = pyrtl.Input(1, 'a')
        b = pyrtl.Input(1, 'b')
        cin = pyrtl.Input(1, 'cin')
        s = pyrtl.Output(1, 's')
        cout = pyrtl.Output(1, 'cout')
        self.module.a <<= a
        self.module.b <<= b
        self.module.cin <<= cin
        s <<= self.module.s
        cout <<= self.module.cout

        sim = pyrtl.Simulation()
        sim.step_multiple({
            'a': '00001111',
            'b': '00110011',
            'cin': '01010101',
        }, {
            's': '01101001',
            'cout': '00010111',
        })

        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(
            output.getvalue(),
            "   a 00001111\n   b 00110011\n cin 01010101\ncout 00010111\n   s 01101001\n"
        )


class TestModIO(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = OneBitAdder()

    def test_bad_input_assignment_outside_module(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__(name="m1")

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(4, 'o')
                o <<= i + 2

        m = M()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w = pyrtl.WireVector(2, 'w')
            w <<= m.i
        self.assertEqual(
            str(ex.exception),
            'Invalid connection (i/2I[m1] -> w/2W). '
            'Argument and destination must belong to same module for these wire types.'
        )

    def test_bad_output_assignment_outside_module(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__(name="m1")

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(4, 'o')
                o <<= i + 2

        m = M()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.o <<= 3
        self.assertTrue(
            str(ex.exception).startswith('Invalid connection')
        )

    def test_bad_outside_wire_connection_to_module(self):
        _ = pyrtl.WireVector(4, 'w')

        class M(pyrtl.Module):
            def __init__(self, name):
                super(M, self).__init__(name=name)

            def definition(self):
                o = self.Output(4, 'o')
                o <<= self.block.wirevector_by_name['w']

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M('m1')
        self.assertEqual(
            str(ex.exception),
            'Invalid connection (w/4W -> o/4O[m1]). '
            'Argument and destination must belong to same module for these wire types.'
        )

    # TODO This *should* be illegal (but currently is not)
    # because it's an assignment to an outside wire while in the definition.
    # A solution might be to check if we're in the definition of the module
    # being assigned to something in its supermodule?
    @unittest.skip
    def test_bad_output_as_arg_to_outside_module(self):
        _ = pyrtl.WireVector(4, 'w')

        class M(pyrtl.Module):
            def __init__(self, name):
                super(M, self).__init__(name=name)

            def definition(self):
                o = self.Output(4, 'o')
                self.block.wirevector_by_name['w'] <<= o
                o <<= 4

        with self.assertRaises(pyrtl.PyrtlError):
            M('m1')

    def test_no_modification_outside_definition(self):
        class A(pyrtl.Module):
            def __init__(self):
                super(A, self).__init__()

            def definition(self):
                a = self.Input(3, 'a')
                b = self.Output(3, 'b')
                b <<= a

        a = A()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _c = a.Input(5, 'c')
        self.assertEqual(
            str(ex.exception),
            "Cannot create a module input outside of the module's definition"
        )

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _c = a.Output(5, 'c')
        self.assertEqual(
            str(ex.exception),
            "Cannot create a module output outside of the module's definition"
        )

    def test_original_names(self):
        self.assertEqual(self.module.a._original_name, 'a')
        self.assertEqual(self.module.b._original_name, 'b')
        self.assertEqual(self.module.cout._original_name, 'cout')
        self.assertEqual(self.module.s._original_name, 's')
        self.assertEqual(self.module.cin._original_name, 'cin')

    def test_to_block_input(self):
        self.module.a.to_block_input('a')
        self.module.b.to_block_input('b')
        self.module.cin.to_block_input('cin')
        block = self.module.block
        for w in self.module.inputs:
            wio = block.get_wirevector_by_name(w._original_name)
            self.assertTrue(isinstance(wio, pyrtl.Input))

    def test_to_block_output(self):
        self.module.s.to_block_output('s')
        self.module.cout.to_block_output('cout')
        block = self.module.block
        for w in self.module.outputs:
            wio = block.get_wirevector_by_name(w._original_name)
            self.assertTrue(isinstance(wio, pyrtl.Output))


class TestDuplicateModules(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_connect_duplicate_modules_bad(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__()

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(3, 'o')
                o <<= i + 1

        m1 = M()
        m2 = M()
        m1.i.to_block_input()
        m2.i.to_block_input()
        m1.o.to_block_output()
        m2.o.to_block_output()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = pyrtl.Simulation()
        self.assertTrue(str(ex.exception).startswith(
            "Duplicate wire names found for the following different signals"))

    def test_connect_duplicate_modules_good(self):
        class M(pyrtl.Module):
            def __init__(self):
                super(M, self).__init__()

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(3, 'o')
                o <<= i + 1

        m1 = M()
        m2 = M()
        m1.i.to_block_input('m1_i')
        m2.i.to_block_input('m2_i')
        m1.o.to_block_output('m1_o')
        m2.o.to_block_output('m2_o')

        sim = pyrtl.Simulation()
        inputs = {
            'm1_i': [1, 2, 3, 0, 1],
            'm2_i': [0, 0, 1, 1, 2],
        }
        outputs = {
            'm1_o': [2, 3, 4, 1, 2],
            'm2_o': [1, 1, 2, 2, 3],
        }
        sim.step_multiple(inputs, outputs)
        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(
            output.getvalue(),
            "m1_i 12301\nm1_o 23412\nm2_i 00112\nm2_o 11223\n"
        )


class TestNestedModules(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = NBitAdder(4)

    def test_access_submodules(self):
        self.assertEqual(len(self.module.submodules), 4)

        self.assertIn(self.module.oba_0, self.module.submodules)
        self.assertIn(self.module.oba_1, self.module.submodules)
        self.assertIn(self.module.oba_2, self.module.submodules)
        self.assertIn(self.module.oba_3, self.module.submodules)

        self.assertEqual(self.module.oba_0.supermodule, self.module)
        self.assertEqual(self.module.oba_1.supermodule, self.module)
        self.assertEqual(self.module.oba_2.supermodule, self.module)
        self.assertEqual(self.module.oba_3.supermodule, self.module)

    def test_all_submodules_have_different_names(self):
        names = set(mod.name for mod in self.module.submodules)
        self.assertEqual(len(names), 4)

    def test_access_submodule_io(self):
        self.assertIn(self.module.oba_0.a, self.module.oba_0.inputs)
        self.assertIn(self.module.oba_0.b, self.module.oba_0.inputs)
        self.assertIn(self.module.oba_0.cin, self.module.oba_0.inputs)
        self.assertIn(self.module.oba_0.s, self.module.oba_0.outputs)
        self.assertIn(self.module.oba_0.cout, self.module.oba_0.outputs)

    def test_bad_assignment_from_submodule_input(self):
        w = pyrtl.WireVector(4)
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w <<= self.module.oba_0.a
        self.assertTrue(
            str(ex.exception).startswith('Invalid connection')
        )

    def test_bad_assignment_to_submodule_output(self):
        w = pyrtl.Const(4)
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            self.module.oba_0.s <<= w
        self.assertTrue(
            str(ex.exception).startswith('Invalid connection')
        )

    def test_correctness(self):
        self.module.to_block_io()
        sim = pyrtl.Simulation()
        sim.step_multiple({
            'a': [0, 1, 2, 3, 8],
            'b': [1, 4, 6, 9, 12],
            'cin': [0, 0, 0, 0, 0],
        }, {
            's': [1, 5, 8, 12, 4],
            'cout': [0, 0, 0, 0, 1],
        })

        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(
            output.getvalue(),
            "   a 01238\n   b 146912\n cin 00000\ncout 00001\n   s 158124\n"
        )


class TestDoubleNestedModules(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_current_module_stack(self):
        tester = self

        class Inner2(pyrtl.Module):
            def __init__(self):
                super(Inner2, self).__init__()

            def definition(self):
                x = self.Input(4, 'x')
                y = self.Output(4, 'y')
                y <<= x - 1
                tester.assertEqual(self.block.current_module, self)
                tester.assertEqual(
                    self.block._current_module_stack,
                    [self.supermodule.supermodule, self.supermodule, self]
                )

        class Inner(pyrtl.Module):
            def __init__(self):
                super(Inner, self).__init__()

            def definition(self):
                a = self.Input(5, 'a')
                b = self.Output(8, 'b')
                m = Inner2()
                m.x <<= a
                b <<= (m.y + 10) * 2
                tester.assertEqual(self.block.current_module, self)
                tester.assertEqual(
                    self.block._current_module_stack,
                    [self.supermodule, self]
                )

        class Outer(pyrtl.Module):
            def __init__(self):
                super(Outer, self).__init__()

            def definition(self):
                a = self.Input(32, 'a')
                b = self.Output(32, 'b')
                in1 = Inner()
                in1.a <<= a + 1
                b <<= in1.b
                tester.assertEqual(self.block.current_module, self)
                tester.assertEqual(
                    self.block._current_module_stack,
                    [self]
                )

        m = Outer()  # Has assertions within the modules
        self.assertIsNone(m.block.current_module)


class TestBadNestedModules(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_bad_assignment_within_nested_to_outside(self):
        class Inner2(pyrtl.Module):
            def __init__(self):
                super(Inner2, self).__init__(name="i2")

            def definition(self):
                x = self.Input(4, 'x')
                y = self.Output(4, 'y')
                y <<= x - 1

        class Inner(pyrtl.Module):
            def __init__(self):
                super(Inner, self).__init__(name="i1")

            def definition(self):
                a = self.Input(4, 'a')
                b = self.Output(8, 'b')
                m = Inner2()
                m.y <<= a  # This should be the problem caught
                b <<= (m.y + 10) * 2

        class Outer(pyrtl.Module):
            def __init__(self):
                super(Outer, self).__init__()

            def definition(self):
                a = self.Input(32, 'a')
                b = self.Output(32, 'b')
                in1 = Inner()
                in1.a <<= a + 1
                b <<= in1.b

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            Outer()
        self.assertEqual(
            str(ex.exception),
            'Invalid connection (a/4I[i1] -> y/4O[i2]). '
            'Argument and destination must belong to same module for these wire types.'
        )


class TestModuleImport(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_module_from_working_block(self):
        a = pyrtl.Input(3, 'a')
        b = pyrtl.Input(4, 'b')
        c = pyrtl.Output(4, 'c')
        d = pyrtl.Output(3, 'd')
        r = pyrtl.Register(3)
        e = a * b
        f = e | (a & b)
        c <<= f + 1
        r.next <<= f + 2
        d <<= r

        self.assertIsNone(pyrtl.working_block().current_module)
        m = pyrtl.module_from_block()
        self.assertIsNone(pyrtl.working_block().current_module)
        self.assertEqual(pyrtl.working_block().toplevel_modules, {m})
        self.assertEqual(pyrtl.working_block().modules, {m})
        self.assertEqual(m.a._original_name, 'a')
        self.assertEqual(m.b._original_name, 'b')
        self.assertEqual(m.c._original_name, 'c')
        self.assertEqual(m.d._original_name, 'd')
        self.assertTrue(isinstance(m.a, pyrtl.module._ModInput))
        self.assertTrue(isinstance(m.b, pyrtl.module._ModInput))
        self.assertTrue(isinstance(m.c, pyrtl.module._ModOutput))
        self.assertTrue(isinstance(m.d, pyrtl.module._ModOutput))

        m.to_block_io()
        sim = pyrtl.Simulation()
        inputs = {
            'a': [1, 4, 6, 2],
            'b': [0, 3, 2, 1],
        }
        outputs = {
            'c': [1, 13, 15, 3],
            'd': [0, 2, 6, 0],
        }
        sim.step_multiple(inputs, outputs)
        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(
            output.getvalue(),
            "a 1462\nb 0321\nc 113153\nd 0260\n"
        )

    def test_module_from_working_block_with_submodules(self):
        # Test all manner of submodule access
        nba = NBitAdder(6, "nba")
        ai = pyrtl.Input(6, 'ai')
        bi = pyrtl.Input(6, 'bi')
        so = pyrtl.Output(6, 'so')
        nba.a <<= ai
        nba.b <<= bi
        nba.cin <<= 0
        so <<= nba.s

        self.assertIsNone(pyrtl.working_block().current_module)
        m = pyrtl.module_from_block()
        self.assertIsNone(pyrtl.working_block().current_module)
        self.assertEqual(pyrtl.working_block().toplevel_modules, {m})
        self.assertEqual(
            pyrtl.working_block().modules,
            {m, nba, nba.oba_0, nba.oba_1, nba.oba_2, nba.oba_3, nba.oba_4, nba.oba_5}
        )
        self.assertEqual(m.ai._original_name, 'ai')
        self.assertEqual(m.bi._original_name, 'bi')
        self.assertEqual(m.so._original_name, 'so')

        self.assertEqual(m.nba.a._original_name, 'a')
        self.assertEqual(m.nba.b._original_name, 'b')
        self.assertEqual(m.nba.cin._original_name, 'cin')
        self.assertEqual(m.nba.s._original_name, 's')
        self.assertEqual(m.nba.cout._original_name, 'cout')

        self.assertEqual(m.submodules, {nba})
        self.assertEqual(nba.supermodule, m)
        self.assertEqual(
            m.nba.submodules,
            {nba.oba_0, nba.oba_1, nba.oba_2, nba.oba_3, nba.oba_4, nba.oba_5}
        )
        self.assertEqual(m.nba.oba_0.supermodule, m.nba)
        self.assertEqual(m.nba.oba_1.supermodule, m.nba)
        self.assertEqual(m.nba.oba_2.supermodule, m.nba)
        self.assertEqual(m.nba.oba_3.supermodule, m.nba)
        self.assertEqual(m.nba.oba_4.supermodule, m.nba)
        self.assertEqual(m.nba.oba_5.supermodule, m.nba)

        for oba in m.nba.submodules:
            self.assertTrue(isinstance(oba.a, pyrtl.module._ModInput))
            self.assertTrue(isinstance(oba.b, pyrtl.module._ModInput))
            self.assertTrue(isinstance(oba.cin, pyrtl.module._ModInput))
            self.assertTrue(isinstance(oba.s, pyrtl.module._ModOutput))
            self.assertTrue(isinstance(oba.cout, pyrtl.module._ModOutput))

# TODO if I can get this working, I'll probably be
# able to import BLIFs with submodules
# (TODO add as a test case in test_inputoutput.py)


if __name__ == "__main__":
    unittest.main()
