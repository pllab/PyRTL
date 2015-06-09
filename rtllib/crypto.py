import sys
sys.path.append("..")
import io
from pyrtl import *


def main():
     #test_mod_exp()
     #test_modulus()
     test_rsa()

def extended_gcd(aa, bb):
    lastremainder, remainder = abs(aa), abs(bb)
    x, lastx, y, lasty = 0, 1, 1, 0
    while remainder:
        lastremainder, (quotient, remainder) = remainder, divmod(lastremainder, remainder)
        x, lastx = lastx - quotient*x, x
        y, lasty = lasty - quotient*y, y
    return lastremainder, lastx * (-1 if aa < 0 else 1), lasty * (-1 if bb < 0 else 1)
 
def modinv(a, m):
    g, x, y = extended_gcd(a, m)
    if g != 1:
        raise ValueError
    return x % m



'''
Here is our current understanding of the full montgomery multiplier process.


We would like c = a * b mod n to happen, but to do so we need to 
go into the montgomery domain.

First we define some variables
k = # of bits in a, b, and n
R = 2^k 
R_inverse = modinv(R, n)

So basically there are 5 steps. 

1) Get the value of precomputed_value - 
We need this value to figure out the a and b residues. 

precomputed_value = R^2 mod n (this requires a modulus unit)

2) Get the a residue:

a_residue = a * precomputed_value mod n

3) Get the b residue: 

b_residue = b * precomputed_value mod n 

4) Get the c residue: 

c_residue = a_residue * b_residue mod n

5) Get the c real value, converted back from the residue value (transform back from montgomery domain)

c = c_residue * 1 mod n 

There's a lot of dense mathematics that's going on here. 

Step 1 is basically precomputing the value of R^2 mod n so that we can 
figure out the a_residue and b_residue values, which are the values in Montgomerys domain.
These values allow for us to do multiplication and modulus very quickly because 
they only require 4 operations: plus, and, modulus by 2, and shift.

Step 2 and 3 give us the a and b residues.

Step 4 gives us the c residue, which is just the montgomery product of the a and b residues.

Step 5 is the transformation step that converts the c_residue back into the normal domain.
This works by multiplying c_residue * 1 and results in C.

The interesting thing is that in every montgomery product operation, there is an implicit
multiplication by R_inverse. This implicit multiplication happens because in the montgomery 
product we shift k times.

A shift by k = dividing by k = dividing by R = multiplying by R_inverse

So that explains why in the beginning we multiply by the precomputed_value because 
R^2 mod n * R_inverse is just R 

'''
def montgomery_multiplier(A,B,N):
    
    #assert len(A) == len(B) == len(N)
    '''

    CHANGE P INTO A REGISTER - store it at each stage of the for loop,
    instead of adding it to the circuit

    '''

    k = len(A)

    P = WireVector(bitwidth = k)
    P <<= 0 
    
    for i in range(0, k):
        P = P + (A & B[i].sign_extended(k))
        #P.name = "p_after_addition" + str(i)

        P = mux(P[0] == 1, falsecase = P, truecase = P + N)  
        #P.name = "p_after_modulus" + str(i)

        P = P[1:]
        #P.name = "p_after_division" + str(i)
        
    
    P = P[:k]
    
    P = mux(P >= N, falsecase = P, truecase = P - N)  
    
    return P

def count_bits(number):
    return len(bin(number).split('b')[1])

def mod_pro(A,B,N,k):
    '''

    CHANGE P INTO A REGISTER - store it at each stage of the for loop,
    instead of adding it to the circuit

    '''

    '''
    p_reg = Register(k, 'i')
    i = Register(k, 'i')
    local_k = Register(k, 'local_k')

    n_reg = Register(len(N), 'n')
    a_reg = Register(len(A), 'a')
    b_reg = Register(len(B), 'b')

    temp_reg1 = Register(k, 'temp_reg1')
    temp_reg2 = Register(k, 'temp_reg2')
    temp_reg3 = Register(k, 'temp_reg3')

    with pyrtl.ConditionalUpdate() as condition:

        with condition(i == 0):
            i.next |= 1
            temp_reg1 |= 0 
            temp_reg2 |= 0 
            temp_reg3 |= 0 
            p_reg |= 0
            local_k |= k - 1

        with condition.fallthrough:
            i.next |= i + 1
            temp_reg1.next |= p_reg + (A & B[i]].sign_extended(k))
            temp_reg2.next |= mux(P[0] == 1, falsecase = temp_reg1, truecase = temp_reg1 + N)  
            temp_reg3.next |= temp_reg2[1:]
            p_reg.next |= temp_reg3

    '''

    P = WireVector(bitwidth = k)
    P <<= 0 

    for i in range(0, k):
        P = P + (A & B[i].sign_extended(k))
        #P.name = "p_after_addition" + str(i)

        P = mux(P[0] == 1, falsecase = P, truecase = P + N)  
        #P.name = "p_after_modulus" + str(i)

        P = P[1:]
        #P.name = "p_after_division" + str(i)


    P = P[:k]

    P = mux(P >= N, falsecase = P, truecase = P - N)  
    
    return P

def mod_exp(m, e, n, nval):
    input_length = len(m)
    3, 4 ,7 
    its_a_one = Const(1, bitwidth = input_length)

    exp = Const(e, bitwidth = count_bits(e))

    h = len(exp)
    c = WireVector(bitwidth = 12)

    c <<= mux(exp[h-1] == 1, falsecase = its_a_one, truecase = m)  

    c2 = WireVector(bitwidth = 12)
    c2 <<= c
    #c.name = "c_before_exp"
    #c2.name = "c2_before_exp"
    for i in range(h-2, -1, -1):

        c2 = c

        c = montgomery_mult(c,c2,n,nval)

        c = mux(exp[i] == 1, falsecase = c, truecase = montgomery_mult(c,m,n,nval))  
    return c


    
def stupid_exp(m,e,n,nval):
    input_length = len(m)
    #precomputed_value = Const(2**(input_length * 2) % nval, bitwidth = input_length)

    #its_a_one = Const(1, bitwidth = input_length)

    #m_residue = WireVector(bitwidth = input_length)
    m2 = WireVector(bitwidth = input_length)
    m2 <<= m
    #accumulator = WireVector(bitwidth = input_length)
    accumulator = montgomery_mult(m,m2,n,nval)
    for i in range(0, e-2):
        #accumulator = montgomery_mult(m,m2,n,nval)
        accumulator = montgomery_mult(accumulator,m,n,nval)
        

    return accumulator

def rsa_encrypt(e,m):
    p = 5
    q = 7
    n = Const(35, bitwidth = 12)

    nval = p * q

    c = mod_exp(m,e, n, nval)

    return c

def rsa_decrypt(d,m):
    p = 5
    q = 7
    n = Const(35, bitwidth = 12)

    nval = p * q

    c = mod_exp(m,d, n, nval)

    return c

def montgomery_mult(a,b,n,nval):
    input_length = len(a)
    precomputed_value = Const(2**(input_length * 2) % nval, bitwidth = input_length)

    its_a_one = Const(1, bitwidth = input_length)

    a_residue = WireVector(bitwidth = input_length)
    b_residue = WireVector(bitwidth = input_length)
    c_residue = WireVector(bitwidth = input_length)

    a_residue <<= mod_pro(a, precomputed_value, n, input_length)
    b_residue <<= mod_pro(b, precomputed_value, n, input_length)
    c_residue <<= mod_pro(a_residue, b_residue, n, input_length)
    return mod_pro(c_residue, its_a_one, n, input_length)

#modular exponentiation will be just like mod addition, 
# except that the additions are replaced with mod multiplications



def test_modulus():
    input_length = 4
    a, b, n = Input(input_length, "a"), Input(input_length, "b"), Input(input_length, "n")

    c = Output(input_length * 2, "Montgomery result")
    
    aval, bval, nval = 3, 2, 7

    c <<= montgomery_mult(a,b,n,nval)
   

    trueval = Output(16, "True Answer")
    trueval <<= (aval * bval) % nval

    sim_trace = SimulationTrace()
    sim = Simulation(tracer=sim_trace)
    sim.step({a: aval, b: bval, n: nval})

    sim_trace.render_trace()
    
    output = sim_trace.trace
    print "Result in Decimal: " + str(output[c])

def test_mod_exp():
    input_length = 6
    a, n = Input(input_length, "a"), Input(input_length, "n")
    
    aval, expval, nval = 3, 5, 7

    c = Output(input_length * expval, "Montgomery result")

    c <<= mod_exp(a,expval,n,nval)

    trueval = Output(16, "True Answer")
    trueval <<= (aval ** expval) % nval

    sim_trace = SimulationTrace()
    sim = Simulation(tracer=sim_trace)
    sim.step({a: aval, n: nval})

    sim_trace.render_trace()
    
    output = sim_trace.trace
    print "Result in Decimal: " + str(output[c])

def test_rsa():
    input_length = 6
    m = Input(input_length, "message")
    
    mval = 10
    c = WireVector(input_length * 2, "Rsa encrypted")

    message_after = Output(input_length * 2, "Rsa decrypted")

    c <<= rsa_encrypt(7, m)

    message_after <<= rsa_decrypt(7, c)

    trueval = Output(16, "True Answer")
    trueval <<= mval

    #print len(working_block().logic)
    #synthesize()
    #print len(working_block().logic)

    sim_trace = SimulationTrace()
    sim = Simulation(tracer=sim_trace)
    sim.step({ m: mval})

    sim_trace.render_trace()
    
    output = sim_trace.trace
    print "Result in Decimal: " + str(output[c])

if __name__ == "__main__":
    main()