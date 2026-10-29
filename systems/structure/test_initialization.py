import unittest
import numpy as np
from controller import Controller

class InitializationTests(unittest.TestCase):
    def test_default_preserves_original_random_initialization_exactly(self):
        for seed in (17,29,43):
            c=Controller(6,100,seed)
            np.testing.assert_array_equal(c.strategy,np.random.default_rng(seed).integers(6,size=200))
    def test_probabilities_and_common_initial_state(self):
        p=np.array([1,1.5,2,1,1.5,2])/9
        a=Controller(6,10000,17,initial_probabilities=p)
        b=Controller(6,10000,17,method='fixed',initial_probabilities=p)
        np.testing.assert_array_equal(a.strategy,b.strategy)
        np.testing.assert_allclose(np.bincount(a.strategy,minlength=6)/20000,p,atol=.01)
    def test_invalid_probabilities_rejected(self):
        with self.assertRaises(ValueError):Controller(2,10,17,initial_probabilities=[.2,.2])

if __name__=='__main__':unittest.main()
