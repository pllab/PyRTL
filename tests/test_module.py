# pylint: disable=no-member

import unittest
import six

import pyrtl


class OneBitAdder(pyrtl.Module):
    def __init__(self, name=""):
        super().__init__(name=name)

    def definition(self):
        a = self.Input(1, 'a')
        b = self.Input(1, 'b')
        cin = self.Input(1, 'cin')
        s = self.Output(1, 's')
        cout = self.Output(1, 'cout')
        s <<= a ^ b ^ cin
        cout <<= (a & b) | (a & cin) | (b & cin)


class NBitAdder(pyrtl.Module):
    def __init__(self, n):
        assert (n > 0)
        self.n = n
        super().__init__()

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
                super().__init__()

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
                super().__init__(name)

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
                super().__init__(name=name)

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

    def test_bad_mod_name(self):
        class M(pyrtl.Module):
            def __init__(self, name):
                super().__init__(name=name)

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
                super().__init__()

            def definition(self):
                a = self.Input(3, 'a')
                b = pyrtl.Const(4)
                a <<= 2 + b

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M()
        self.assertEqual(
            str(ex.exception),
            "Module must have at least one output."
        )

    def test_empty_io_name(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()

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
                super().__init__()

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
                super().__init__(name=name)

            def definition(self):
                o = self.Output(4, 'o')
                o <<= 4
        a = A('m1')
        with self.assertRaises(AttributeError) as ex:
            a.x
        self.assertEqual(
            str(ex.exception),
            'Cannot get non-IO wirevector "x" from module.\n'
            'Make sure you spelled the wire name correctly, '
            'that you used "self.Input" and "self.Output" rather than '
            '"pyrtl.Input" and "pyrtl.Output" to declare the IO wirevectors, '
            'and that you are accessing it from the correct module.\n'
            'Available input wires are [] and output wires are [\'o/4O(m1)\'].'
        )

    def test_unconnected_inputs(self):
        class A(pyrtl.Module):
            def __init__(self, name):
                super().__init__(name=name)

            def definition(self):
                i = self.Input(4, 'i')
                o = self.Output(4, 'o')
                o <<= 4
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            A('m1')
        self.assertEqual(
            str(ex.exception),
            'Invalid module. Input "i/4I(m1)" is not connected '
            'to any internal module logic.'
        )

    def test_unconnected_outputs(self):
        class A(pyrtl.Module):
            def __init__(self, name):
                super().__init__(name=name)

            def definition(self):
                o = self.Output(4, 'o')
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            A('m1')
        self.assertEqual(
            str(ex.exception),
            'Invalid module. Output "o/4O(m1)" is not connected '
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
                super().__init__(name=name)

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                i <<= 3
                o <<= i

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            M('m1')
        self.assertEqual(
            str(ex.exception),
            'Invalid module. Module input "i/2I(m1)" cannot be '
            'used as a destination to a net within a module definition.'
        )


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

    def test_cannot_create_module_wires_outside_definition(self):
        # TODO either check the current module in the block,
        # or check if we're within the module's definition via the 'in_definition' flag...
        pass

    @unittest.skip
    def test_bad_input_assignment_outside_module(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(4, 'o')
                o <<= i + 2

        m = M()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w = pyrtl.WireVector(2)
            w <<= m.i
        self.assertEqual(
            str(ex.exception),
            "Invalid module. Module input i/2W can only "
            "be used on the rhs of <<= while within a module definition."
        )

    @unittest.skip
    def test_bad_output_assignment_outside_module(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(4, 'o')
                o <<= i + 2

        m = M()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m.o <<= 3
        self.assertEqual(
            str(ex.exception),
            "Invalid module. Module output o/4W can only "
            "be used on the lhs of <<= while within a module definition."
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

    @unittest.skip
    def test_bad_assignment_from_submodule_input(self):
        w = pyrtl.WireVector(4)
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            w <<= self.module.oba_0.a
        self.assertEqual(
            str(ex.exception),
            'TODO'
        )

    @unittest.skip
    def test_bad_assignment_to_submodule_output(self):
        w = pyrtl.Const(4)
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            self.module.oba_0.s <<= w
        self.assertEqual(
            str(ex.exception),
            'TODO'
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
                super().__init__()

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
                super().__init__()

            def definition(self):
                a = self.Input(4, 'a')
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
                super().__init__()

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
    # You should only be able to put input into modules that
    # are immediately accessible (block.modules, or module.submodules
    # if within a definition.
    # Likewise, you should only be able to get the output from modules
    # that immediately accessible.
    # Sibling modules can also be connected.
    # -----------------------------------------------------------
    # | block                                                   |
    # |    -----------     ------------------------------|      |
    # |    | module1 |     | module2                     |      |
    # o<---o         o---> i ------+8------w             |      |
    # i--->i         |     |   ----------- |   --------  |      |
    # |    -----------     |   | module3 | \-->i mod4 |  |      |
    # |                    |   |         |     |      |  |      |
    # i------------------->i-->i         o---->i      o->o--+7->o
    # |                    |   -----------     --------  |      |
    # |                    -------------------------------      |
    # ----------------------------------------------------------|

    def setUp(self):
        pyrtl.reset_working_block()

    @unittest.skip
    def test_bad_assignment_within_nested_to_outside(self):
        class Inner2(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(4, 'x')
                y = self.Output(4, 'y')
                y <<= x - 1

        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(4, 'a')
                b = self.Output(8, 'b')
                m = Inner2()
                m.y <<= a  # This should be the problem caught
                b <<= (m.y + 10) * 2

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

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
            'TODO'
        )


if __name__ == "__main__":
    unittest.main()
