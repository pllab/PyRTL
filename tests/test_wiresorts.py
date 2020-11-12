# pylint: disable=no-member
# pylint: disable=unbalanced-tuple-unpacking

import unittest
import six

import pyrtl
from pyrtl.rtllib import fifos

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
            oba = self.submod(OneBitAdder())
            oba.a <<= a[i]
            oba.b <<= b[i]
            oba.cin <<= cin
            ss.append(oba.s)
            cin = oba.cout
        s <<= pyrtl.concat_list(ss)
        cout <<= cin

class TestWireSortSimpleModule(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = fifos.Fifo(8, 4)

    def test_wire_sorts(self):
        f = fifos.Fifo(8, 4)
        self.assertTrue(isinstance(f.reset.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.valid_in.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.data_in.sort, pyrtl.wiresorts.Free))
        self.assertTrue(isinstance(f.ready_in.sort, pyrtl.wiresorts.Free))

        self.assertTrue(isinstance(f.ready_out.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(f.valid_out.sort, pyrtl.wiresorts.Giving))
        self.assertTrue(isinstance(f.data_out.sort, pyrtl.wiresorts.Giving))

class TestWireSortSimpleModuleCombinational(unittest.TestCase):
    pass

class TestWireSortNestedModules(unittest.TestCase):
    pass

class TestWireSortNestedModulesCombinational(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
        self.module = NBitAdder(4)
    
    def testSortCaching(self):
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