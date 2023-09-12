"""Module defining TRNG helper methods and classes

Farore has the ability to utilize True Random Number Generation (TRNG)
when performing dice rolls, slot machine spins, and gacha pulls.
Realistically, this isn't very useful, but it is pretty freaking cool.

The way this works is via a TRNG system I wrote called IttoRNG, which runs
as a webserver on a raspberry pi. The RNG provided by that system is truly random
via the RNG function of the Broadcom SoC. Thus, by serving this random
information over a webserver, Farore can also generate random numbers.

    * itto_seed - Coroutine which obtains a set number of random bytes in the specified format from IttoRNG
    * TRNG - Class which implements a TRNG seed pool which can be sampled from. Good for large RNG operations
    * get_seed - Coroutine which obtains a 32 byte integer seed

The subsequent coroutines are all async TRNG parallels to Python's random library. 
"""

from azura.core.conf import Config

conf = Config.load()

from azura.ext.utils import aio_get

import random


async def itto_seed(bytes, format="int"):
    return await aio_get(f"{conf.trng.endpoint}/{format}/{bytes}")


class TRNG:
    def __init__(self, pool_size, sample_size):
        self.pool_size = pool_size
        self.sample_size = sample_size
        self._pool = ""

    @classmethod
    async def seed(cls, pool_size=1024, sample_size=8):
        trng = cls(pool_size, sample_size)
        trng._pool = await itto_seed(pool_size)
        return trng
    
    async def reseed(self):
        return await self.__class__.seed(pool_size=self.pool_size, sample_size=self.sample_size)
    
    def _get_seed(self):
        if len(self._pool) < self.sample_size:
            raise ValueError("The pool has been exhausted and must be reseeded.")
        
        random.seed()
        seed = "".join(random.sample(self._pool, self.sample_size))
        self._pool.replace(seed, "")
        return seed
    
    def randint(self, lwr, upr):
        random.seed(self._get_seed())
        return random.randint(lwr, upr)
    
    def choice(self, l):
        random.seed(self._get_seed())
        return random.choice(l)
    
    def choices(self, l, weights=None, cum_weights=None, k=1):
        random.seed(self._get_seed())
        return random.choices(l, weights=weights, cum_weights=cum_weights, k=k)
    
    def uniform(self, lwr, upr):
        random.seed(self._get_seed())
        return random.uniform(lwr, upr)
    
    def sample(self, l, k):
        random.seed(self._get_seed())
        return random.sample(l, k)


async def get_seed():
    return await itto_seed(32)


async def randint(lwr, upr):
    random.seed((await get_seed()))
    return random.randint(lwr, upr)


async def choice(l):
    random.seed((await get_seed()))
    return random.choice(l)


async def choices(l, weights=None, cum_weights=None, k=1):
    random.seed((await get_seed()))
    return random.choices(l, weights=weights, cum_weights=cum_weights, k=k)


async def uniform(lwr, upr):
    random.seed((await get_seed()))
    return random.uniform(lwr, upr)


async def sample(l, k):
    random.seed((await get_seed()))
    return random.sample(l, k)
