import unittest
import pyrtl

class TestSimple(unittest.TestCase):

    class Simple(pyrtl.Module):
        def __init__(self):
            super().__init__()

        def definition(self):
            a = self.Input(2, 'a')
            b = self.Output(6, 'b')
            b <<= a * 4

    def setUp(self):
        pyrtl.reset_working_block()

    def test_well_connected(self):
        s = TestSimple.Simple()
        a_in = pyrtl.Input(2, 'a_in')
        b_out = pyrtl.Output(6, 'b_out')
        s['a'] <<= a_in
        b_out <<= s['b']

        sim = pyrtl.Simulation()
        sim.step_multiple({'a_in': [1,2,3]}, {'b_out': [4, 8, 12]})

    def test_ill_connected(self):
        s = TestSimple.Simple()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            s['a'] <<= s['b']
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

if __name__ == '__main__':
    unittest.main()