# this example demonstrates how to build big networks using rematerialzation and scan to reduce memory footprint compilation size. 

import numpy as np

from flax.core import Scope, init, apply, unfreeze, lift

from flax import nn

import jax
from jax import lax, random, numpy as jnp

from typing import Any
from functools import partial


Array = Any


default_norm = partial(nn.batch_norm)

def residual_block(scope: Scope, x: Array, conv, norm, act, features: int):
  residual = x
  x = scope.child(conv, 'conv_1')(x, features, (3, 3))
  x = scope.child(norm, 'bn_1')(x)
  x = act(x)
  x = scope.child(conv, 'conv_2')(x, features, (3, 3))
  x = scope.child(norm, 'bn_2')(x)

  if x.shape != residual.shape:
    residual = scope.child(conv, 'proj_conv')(residual, 4 * features, (1, 1))
    residual = scope.child(norm, 'proj_bn')(residual)

  return act(residual + x)


def big_resnet(scope: Scope, x, blocks=(10, 10), dtype=jnp.float32,
               norm=default_norm, act=nn.relu):
  conv = partial(nn.conv, bias=False, dtype=dtype)
  norm = partial(norm, dtype=dtype)

  # a two stage resnet where inner blocks are rematerialized to make sure
  # memory consumtion grows as O(sqrt(N)) and compute is O(N) where N is the number of blocks..
  # we use a double scan such that the compiled binary is of size O(1).
  print('total residual blocks:', np.prod(blocks))

  def body_fn(scope, x):
    return residual_block(scope, x, conv, norm, act, features=x.shape[-1])

  return lift.remat_scan(
      body_fn, scope, x, lengths=blocks,
      variable_modes={'param': 'scan', 'batch_stats': 'scan'},
      split_rngs={'param': True})

if __name__ == "__main__":
  x = random.normal(random.PRNGKey(0), (1, 8, 8, 8))
  y, params = init(big_resnet)(random.PRNGKey(1), x)
  print(y.shape)
  print(jax.tree_map(jnp.shape, unfreeze(params)))