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
        self.assertTrue(isinstance(m['a'].sort, pyrtl.helpfulness.Needed))
        self.assertTrue(isinstance(m['b'].sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(m['a'].sort.awaited_by_set, {m['b']})
        self.assertEqual(m['b'].sort.requires_set, {m['a']})
    
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
        self.assertEqual(m['a'].sort.awaited_by_set, {m['c']})
        self.assertTrue(isinstance(m['b'].sort, pyrtl.helpfulness.Needed))
        self.assertEqual(m['b'].sort.awaited_by_set, {m['c']})
        self.assertTrue(isinstance(m['c'].sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(m['c'].sort.requires_set, {m['a'], m['b']})
        self.assertTrue(isinstance(m['d'].sort, pyrtl.helpfulness.Giving))
        self.assertFalse(m['d'].sort.requires_set)

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
        self.assertEqual(i['x'].sort.awaited_by_set, {i['y']})
        self.assertTrue(isinstance(i['y'].sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(i['y'].sort.requires_set, {i['x']})
        o = Outer()
        self.assertTrue(isinstance(o['i'].sort, pyrtl.helpfulness.Needed))
        self.assertEqual(o['i'].sort.awaited_by_set, {o['o_foo']})
        self.assertTrue(isinstance(o['o_foo'].sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(o['o_foo'].sort.requires_set, {o['i']})

    def test_nested_connection_with_state(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                x = self.Input(6, 'x')
                r = pyrtl.Register(6)
                r.next <<= x
                y = self.Output(7, 'y')
                y <<= r + 4

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(6, 'i')
                o = self.Output(7, 'o_foo')
                b = Inner()
                b['x'] <<= i
                o <<= b['y']

        i = Inner()
        self.assertTrue(isinstance(i['x'].sort, pyrtl.helpfulness.Free))
        self.assertFalse(i['x'].sort.awaited_by_set)
        self.assertTrue(isinstance(i['y'].sort, pyrtl.helpfulness.Giving))
        self.assertFalse(i['y'].sort.requires_set)
        o = Outer()
        self.assertTrue(isinstance(o['i'].sort, pyrtl.helpfulness.Free))
        self.assertFalse(o['i'].sort.awaited_by_set)
        self.assertTrue(isinstance(o['o_foo'].sort, pyrtl.helpfulness.Giving))
        self.assertFalse(o['o_foo'].sort.requires_set)

    def test_nested_connection_with_state2(self):
        class Inner(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                w = self.Input(1, 'w')
                x = self.Input(6, 'x')
                r = pyrtl.Register(6)
                r.next <<= x
                y = self.Output(7, 'y')
                y <<= r + 4 + w

        class Outer(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                i = self.Input(6, 'i')
                j = self.Input(1, 'j')
                o = self.Output(7, 'o_foo')
                b = Inner()
                b['x'] <<= i
                b['w'] <<= j
                o <<= b['y']

        i = Inner()
        self.assertTrue(isinstance(i['x'].sort, pyrtl.helpfulness.Free))
        self.assertFalse(i['x'].sort.awaited_by_set)
        self.assertTrue(isinstance(i['y'].sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(i['y'].sort.requires_set, {i['w']})
        o = Outer()
        self.assertTrue(isinstance(o['i'].sort, pyrtl.helpfulness.Free))
        self.assertFalse(o['i'].sort.awaited_by_set)
        self.assertTrue(isinstance(o['j'].sort, pyrtl.helpfulness.Needed))
        self.assertEqual(o['j'].sort.awaited_by_set, {o['o_foo']})
        self.assertTrue(isinstance(o['o_foo'].sort, pyrtl.helpfulness.Dependent))
        self.assertEqual(o['o_foo'].sort.requires_set, {o['j']})

if __name__ == '__main__':
    unittest.main()