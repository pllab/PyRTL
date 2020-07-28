# pylint: disable=unbalanced-tuple-unpacking
import pyrtl
import unittest
import pyrtl

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

    class NotAllConnected(pyrtl.Module):
        def __init__(self):
            super().__init__()
    
        def definition(self):
            # Trivial, because Python will warn about unused variable.
            _i = self.Input(2, 'i')
            o = self.Output(2, 'o')
            o <<= 1

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
    
    def test_not_all_internally_connected(self):
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            _ = TestNestedConnection.NotAllConnected()
        self.assertEqual(str(ex.exception),
            f"Invalid module. Input i/2W is not connected to any internal module logic."
        )

if __name__ == "__main__":
    unittest.main()