# pylint: disable=unbalanced-tuple-unpacking
import pyrtl
import unittest
import pyrtl

class TestGoodModule(unittest.TestCase):

    class A(pyrtl.Module):
        def __init__(self):
            super().__init__()

        def definition(self):
            a = self.Input(3, 'a')
            b = self.Input(4, 'b')
            c = self.Output(4, 'c')
            d = self.Output(3, 'd')
            c <<= a + 1
            d <<= c + b - 2

    def setUp(self):
        pyrtl.reset_working_block()
    
    def test_well_connected(self):
        a = TestGoodModule.A()
        self.assertFalse(a['a'].externally_connected())
        self.assertFalse(a['b'].externally_connected())

class TestBadModule(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_bad_input_assignment_in_module(self):
        class M(pyrtl.Module):
            # Problem: tries to assign to an input within a module
            def __init__(self):
                super().__init__()
            
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                i <<= 3
                o <<= i

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = M()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Module input i/2W cannot be used on the "
             "lhs of <<= while within a module definition."
        )

    def test_bad_output_assignment_in_module(self):
        class M(pyrtl.Module):
            # Problem: tries to assign output to a value within a module
            def __init__(self):
                super().__init__()
            
            def definition(self):
                i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                _w = i + 3
                v = pyrtl.WireVector(5)
                v <<= o

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = M()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Module output o/2W cannot be used on the "
            "rhs of <<= while within a module definition."
        )

    def test_not_all_internally_connected(self):
        class M(pyrtl.Module):
            # Problem: not all inputs are connected to internal logic (i.e. unused io)
            def __init__(self):
                super().__init__()
        
            def definition(self):
                # Trivial, because Python will warn about unused variable.
                _i = self.Input(2, 'i')
                o = self.Output(2, 'o')
                o <<= 1

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = M()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Input i/2W is not connected to any internal module logic."
        )

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
            w <<= m['i']
        self.assertEqual(str(ex.exception),
            "Invalid module. Module output i/2W can only "
            "be used on the rhs of <<= while within a module definition.")

        pass

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
            m['o'] <<= 3
        self.assertEqual(str(ex.exception),
            "Invalid module. Module output o/4W can only "
            "be used on the lhs of <<= while within a module definition.")

class TestDifferentSizes(unittest.TestCase):

    class A(pyrtl.Module):
        def __init__(self):
            super().__init__()

        def definition(self):
            ain = self.Input(6, 'ain')
            o = self.Output(6, 'o')
            o <<= ain + 3

    class B(pyrtl.Module):
        def __init__(self):
            super().__init__()

        def definition(self):
            i = self.Input(5, 'i')
            bout = self.Output(5, 'bout')
            bout <<= i

    def setUp(self):
        pyrtl.reset_working_block()

    def test_connect(self):
        a = TestDifferentSizes.A()
        b = TestDifferentSizes.B()
        b['i'] <<= a['o']

        a["ain"].to_pyrtl_input()
        b["bout"].to_pyrtl_output()

        inputs = {
            'ain': [11, 10, 9]
        }
        outputs = {
            'bout': [14, 13, 12]
        }

        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, outputs)


class TestNestedConnection(unittest.TestCase):

    class A(pyrtl.Module):
        def __init__(self):
            super().__init__()

        def definition(self):
            a = self.Input(2, 'a')
            b = self.Input(2, 'b')
            c = self.Input(2, 'c')
            o = self.Output(5, 'o_counter')
            o <<= a + b * c

    class B(pyrtl.Module):
        def __init__(self):
            super().__init__()

        def definition(self):
            x = self.Input(6, 'x')
            y = self.Output(7, 'y')
            y <<= x + 4

    class Nested(pyrtl.Module):
        def __init__(self):
            super().__init__()

        def definition(self):
            i = self.Input(6, 'i')
            o = self.Output(7, 'o_foo')
            b = TestNestedConnection.B()
            # Case: outer mod input to nested mod input
            b['x'] <<= i
            # Case: nested mod output to outer mod output
            o <<= b['y']

    def setUp(self):
        pyrtl.reset_working_block()

    def test_connection(self):
        a = TestNestedConnection.A()
        f = TestNestedConnection.Nested()
        f['i'] <<= a['o_counter']

        a_in, b_in, c_in = pyrtl.input_list('a_in/2 b_in/2 c_in/2')
        a['a'] <<= a_in
        a['b'] <<= b_in
        a['c'] <<= c_in

        out_foo = pyrtl.Output(7, 'out_foo')
        out_foo <<= f['o_foo']

        inputs = {'a_in': [1], 'b_in': [2], 'c_in': [3]}
        outputs = {'out_foo': [11]}
        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, outputs)

    def test_connection_io_shorthand(self):
        a = TestNestedConnection.A()
        f = TestNestedConnection.Nested()

        f['i'] <<= a['o_counter']

        a['a'].to_pyrtl_input()
        a['b'].to_pyrtl_input()
        a['c'].to_pyrtl_input()
        f['o_foo'].to_pyrtl_output()

        inputs = {'a': [1], 'b': [2], 'c': [3]}
        outputs = {'o_foo': [11]}
        sim = pyrtl.Simulation()
        sim.step_multiple(inputs, outputs)

if __name__ == "__main__":
    unittest.main()