import unittest
import pyrtl

class TestHelpfulness(unittest.TestCase):

    class M(pyrtl.Module):
        def __init__(self, name=""):
            super().__init__(name=name)

        def definition(self):
            a = self.Input(4, 'a')
            b = self.Output(6, 'b')
            b <<= a * 4

    def setUp(self):
        pyrtl.reset_working_block()

    def test_single_connected(self):
        m = TestHelpfulness.M()
        a_in = pyrtl.Input(4, 'a_in')
        b_out = pyrtl.Output(6, 'b_out')
        m['a'] <<= a_in + 1 # +1 to make sure we don't rely on direct connection to Pyrtl.Input
        b_out <<= m['b'] - 1 # +1 ditto for output

        sim = pyrtl.Simulation()
        sim.step_multiple({'a_in': [1,2,3]}, {'b_out': [7, 11, 15]})
        self.assertTrue(m['a'].sort, pyrtl.helpfulness.Needed)
        self.assertTrue(m['b'].sort, pyrtl.helpfulness.Dependent)
        self.assertTrue(m['b'] in m['a'].sort.awaited_by_set)
        self.assertTrue(m['a'] in m['b'].sort.requires_set)
    
    def test_three_connected_simple_cycle_no_state(self):
        m1 = TestHelpfulness.M(name="m1")
        m2 = TestHelpfulness.M(name="m2")
        m3 = TestHelpfulness.M(name="m3")
        m2['a'] <<= m1['b']
        m3['a'] <<= m2['b']
        m1['a'] <<= m3['b']  # TODO test from here

    # TODO add rest of simple cases, three or more modules, modules with state, check for expected wire sorts
    # TODO add in my larger test files

    def test_ill_connected(self):
        m = TestHelpfulness.M()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m['a'] <<= m['b']
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

if __name__ == '__main__':
    unittest.main()