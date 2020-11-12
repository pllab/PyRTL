# pylint: disable=no-member

import unittest
import six

import pyrtl


class OneBitAdder(pyrtl.Module):
    def __init__(self):
        super().__init__()

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
            # oba = OneBitAdder()  # Doing this is legal, but won't register it with the supermodule
            oba = self.submod(OneBitAdder())
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

    def test_several_modules_instantiated(self):
        class M(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                a = self.Input(3, name='a')
                b = self.Output(3, name='b')
                b <<= a

        m1 = M()
        m2 = M()
        for module in pyrtl.working_block().modules:
            self.assertTrue(module.name.startswith('mod_'))
        self.assertEqual(set(pyrtl.working_block().modules), {m1, m2})

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

    def test_unique_io_names(self):
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


class TestSimpleModule(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = OneBitAdder()

    def test_internal_names(self):
        self.assertTrue

    def testInputs(self):
        self.assertEqual(self.module.inputs, {self.module.a, self.module.b, self.module.cin})

    def testOutputs(self):
        self.assertEqual(self.module.outputs, {self.module.s, self.module.cout})

    def testToBlockIO(self):
        block = self.module.block
        self.assertEqual(block.wirevector_subset((pyrtl.Input, pyrtl.Output)), set())
        self.module.to_block_io()
        for w in self.module.inputs:
            wio = block.get_wirevector_by_name(w._original_name)
            self.assertTrue(isinstance(wio, pyrtl.Input))
        for w in self.module.outputs:
            wio = block.get_wirevector_by_name(w._original_name)
            self.assertTrue(isinstance(wio, pyrtl.Output))

    def testWiresHaveModuleAttribute(self):
        # starting from inputs, trace all wires
        # connected to them through to the outputs,
        # and check they all have the correct module annotation.
        # care must be taken for submodules...what is the property we
        # are tracking there, because we must allow wires of different
        # modules to be connected, if it's to a submodule....
        pass

    def testCorrectness(self):
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

    def testCannotCreateOutsideDefinition(self):
        # TODO either check the current module in the block,
        # or check if we're within the module's definition via the 'in_definition' flag...
        pass

    def testOriginalNames(self):
        self.assertEqual(self.module.a._original_name, 'a')
        self.assertEqual(self.module.b._original_name, 'b')
        self.assertEqual(self.module.cout._original_name, 'cout')
        self.assertEqual(self.module.s._original_name, 's')
        self.assertEqual(self.module.cin._original_name, 'cin')

    def testToBlockInput(self):
        self.module.a.to_block_input('a')
        self.module.b.to_block_input('b')
        self.module.cin.to_block_input('cin')
        block = self.module.block
        for w in self.module.inputs:
            wio = block.get_wirevector_by_name(w._original_name)
            self.assertTrue(isinstance(wio, pyrtl.Input))

    def testToBlockOutput(self):
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

    def testAccessSubmodules(self):
        # TODO able to access internal modules and their internal i/o...
        pass

    def testCorrectness(self):
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


if __name__ == "__main__":
    unittest.main()
