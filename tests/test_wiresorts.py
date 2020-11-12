# pylint: disable=no-member
# pylint: disable=unbalanced-tuple-unpacking

import unittest
import six

import pyrtl
from pyrtl.rtllib import fifos

class TestSimpleModules(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()

    def test_fifo_wire_sorts(self):
        f = fifos.Fifo(8, 4)
        self.assertTrue(isinstance(f.reset.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.valid_in.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.data_in.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.ready_in.sort, pyrtl.wiresorts.Free))

        self.assertTrue(isinstance(f.ready_out.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(f.valid_out.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(f.data_out.sort, pyrtl.wiresorts.Giving))

    def test_wire_sort_in_module(self):
        class T(pyrtl.Module):
            def __init__(self):
                super().__init__()

            def definition(self):
                r = pyrtl.Register(1, 'r')
                w1 = self.Input(1, 'w1')
                w2 = self.Input(1, 'w2')
                w3 = self.Input(1, 'w3')
                w4 = self.Input(1, 'w4')
                w8 = self.Output(1, 'w8')
                w9 = self.Output(1, 'w9')
                w5 = w1 & w2
                w10 = pyrtl.Const(0)
                r.next <<= w5 | w3
                w8 <<= r ^ w10
                w6 = ~w4
                w7 = r ^ w6
                w9 <<= w7 | w1

        t = T()
        self.assertTrue(isinstance(t.w1.sort, pyrtl.wiresorts.Needed))
        self.assertEqual(t.w1.sort.needed_by_set, {t.w9})
        self.assertTrue(isinstance(t.w2.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(t.w3.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(t.w4.sort, pyrtl.wiresorts.Needed))
        self.assertEqual(t.w4.sort.needed_by_set, {t.w9})
        self.assertTrue(isinstance(t.w8.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(t.w9.sort, pyrtl.wiresorts.Dependent))
        self.assertEqual(t.w9.sort.depends_on_set, {t.w1, t.w4})
    
class TestMultipleIntraModules(unittest.TestCase):
    class M(pyrtl.Module):
        def __init__(self, name=""):
            super().__init__(name=name)

        def definition(self):
            a = self.Input(4, 'a')
            b = self.Output(6, 'b')
            b <<= a * 4

    class N(pyrtl.Module):
        def __init__(self, name=""):
            super().__init__(name=name)

        def definition(self):
            a = self.Input(4, 'a')
            b = self.Output(6, 'b')
            r = pyrtl.Register(5, 'r')
            r.next <<= a + 1
            b <<= r * 4
    
    def setUp(self):
        pyrtl.reset_working_block()

    def test_single_connected(self):
        m = TestMultipleIntraModules.M()
        a_in = pyrtl.Input(4, 'a_in')
        b_out = pyrtl.Output(6, 'b_out')
        m.a <<= a_in + 1
        b_out <<= m.b - 1

        sim = pyrtl.Simulation()
        sim.step_multiple({'a_in': [1,2,3]}, {'b_out': [7, 11, 15]})

        output = six.StringIO()
        sim.tracer.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), " a_in 123\nb_out 71115\n")

        self.assertTrue(isinstance(m.a.sort, pyrtl.wiresorts.Needed))
        self.assertTrue(isinstance(m.b.sort, pyrtl.wiresorts.Dependent))
        self.assertEqual(m.a.sort.needed_by_set, {m.b})
        self.assertEqual(m.b.sort.depends_on_set, {m.a})
    
    def test_three_connected_simple_cycle_no_state(self):
        # TODO continue from here, adding in my previous intra-checks
        m1 = TestMultipleIntraModules.M()
        m2 = TestMultipleIntraModules.M()
        m3 = TestMultipleIntraModules.M()
        m2.a <<= m1.b
        m3.a <<= m2.b
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            m1.a <<= m3.b
        self.assertTrue(str(ex.exception).startswith("Connection error!"))
    
    # TODO possibly add the reachability tests

class TestNestedModules(unittest.TestCase):

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
                # oba = OneBitAdder()
                oba = self.submod(TestNestedModules.OneBitAdder())
                oba.a <<= a[i]
                oba.b <<= b[i]
                oba.cin <<= cin
                ss.append(oba.s)
                cin = oba.cout
            s <<= pyrtl.concat_list(ss)
            cout <<= cin

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = TestNestedModules.NBitAdder(4)
    
    def test_sort_caching_correct(self):
        # For each submodule, verify the wiresorts are correct, meaning we didn't
        # just copy the sort via caching, but actually got the corresponding io
        # wire for each submodule.
        for oba in self.module.submodules:
            self.assertTrue(isinstance(oba.a.sort, pyrtl.wiresorts.Needed))
            self.assertTrue(oba.a.sort.needed_by_set, {oba.s, oba.cout})
            self.assertTrue(isinstance(oba.b.sort, pyrtl.wiresorts.Needed))
            self.assertTrue(oba.b.sort.needed_by_set, {oba.s, oba.cout})
            self.assertTrue(isinstance(oba.cin.sort, pyrtl.wiresorts.Needed))
            self.assertTrue(oba.cin.sort.needed_by_set, {oba.s, oba.cout})
            self.assertTrue(isinstance(oba.s.sort, pyrtl.wiresorts.Dependent))
            self.assertTrue(oba.s.sort.depends_on_set, {oba.a, oba.b, oba.cin})
            self.assertTrue(isinstance(oba.cout.sort, pyrtl.wiresorts.Dependent))
            self.assertTrue(oba.cout.sort.depends_on_set, {oba.a, oba.b, oba.cin})


if __name__ == "__main__":
    unittest.main()