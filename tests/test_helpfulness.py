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
        m['a'] <<= a_in + 1
        b_out <<= m['b'] - 1

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
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m1['a'] <<= m3['b']
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

    def test_ill_connected(self):
        m = TestHelpfulness.M()

        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m['a'] <<= m['b']
        self.assertTrue(str(ex.exception).startswith("Connection error!"))

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

        m = pyrtl.module_from_block()
        self.assertTrue(isinstance(m['a'].sort, pyrtl.helpfulness.Needed))
        self.assertTrue(isinstance(m['b'].sort, pyrtl.helpfulness.Needed))
        self.assertTrue(isinstance(m['c'].sort, pyrtl.helpfulness.Dependent))
        self.assertTrue(isinstance(m['d'].sort, pyrtl.helpfulness.Giving))

    def test_nested_connection(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(6, 'x')
                y = self.Output(7, 'y')
                y <<= x + 4

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(6, 'i')
                o = self.Output(7, 'o_foo')
                b = Inner()
                # Case: outer mod input to nested mod input
                b['x'] <<= i
                # Case: nested mod output to outer mod output
                o <<= b['y']

        i = Inner()
        self.assertTrue(isinstance(i['x'].sort, pyrtl.helpfulness.Needed))
        self.assertTrue(isinstance(i['y'].sort, pyrtl.helpfulness.Dependent))
        o = Outer()
        self.assertTrue(isinstance(o['i'].sort, pyrtl.helpfulness.Needed))
        self.assertTrue(isinstance(o['o_foo'].sort, pyrtl.helpfulness.Dependent))

    def test_nested_connection_with_state(self):
        # TODO
        pass

if __name__ == '__main__':
    unittest.main()