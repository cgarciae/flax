import jax
from jax import numpy as jnp, random, lax
from flax import nn
from flax.nn import initializers
from typing import Any, Callable, Iterable, List, Optional, Tuple, Type, Union
from flax.linen import Module, MultiModule
import numpy as np


# A concise MLP defined via lazy submodule initialization
class MLP(Module):
  widths: Iterable

  def __call__(self, x):
    for width in self.widths[:-1]:
      x = nn.relu(Dense(self, width)(x))
    return Dense(self, self.widths[-1])(x)


# An autoencoder exposes multiple methods, so we extend from MultiModule
# and define all submodules in setup().
class AutoEncoder(MultiModule):
  encoder_widths: Iterable
  decoder_widths: Iterable
  input_shape: Tuple = None

  def setup(self):
    # Submodules attached in `setup` get names via attribute assignment
    self.encoder = MLP(self, self.encoder_widths)
    self.decoder = MLP(self, self.decoder_widths + (jnp.prod(self.input_shape), ))

  def __call__(self, x):
    return self.decode(self.encode(x))

  def encode(self, x):
    assert x.shape[-len(self.input_shape):] == self.input_shape
    return self.encoder(jnp.reshape(x, (x.shape[0], -1)))

  def decode(self, z):
    z = self.decoder(z)
    x = nn.sigmoid(z)
    x = jnp.reshape(x, (x.shape[0],) + self.input_shape)
    return x


# `ae` is a detached module, which has no variables.
ae = AutoEncoder(
  parent=None,
  encoder_widths=(32, 32, 32),
  decoder_widths=(32, 32, 32),
  input_shape=(28, 28, 1))


# `ae.initialized` returnes a materialized copy of `ae` by
# running through an input to create submodules defined lazily.
ae = ae.initialized(
  {'param': random.PRNGKey(42)},
  jnp.ones((1, 28, 28, 1)))


# Now you can use `ae` as a normal object, calling any methods defined on AutoEncoder
print("reconstruct", jnp.shape(ae(jnp.ones((1, 28, 28, 1)))))
print("encoder", jnp.shape(ae.encode(jnp.ones((1, 28, 28, 1)))))


# `ae.variables` is a frozen dict that looks like
# {"param": {"decoder": {"Dense_0": {"bias": ..., "kernel": ...}, ...}}
print("var shapes", jax.tree_map(jnp.shape, ae.variables))


# You can access submodules defined in setup(), they are just references on
# the autoencoder instance
encoder = ae.encoder
print("encoder var shapes", jax.tree_map(jnp.shape, encoder.variables))


# You can also acccess submodules that were defined in-line.
# (We may add syntactic sugar here, e.g. to allow `ae.encoder.Dense_0`)
encoder_dense0 = ae.encoder.children['Dense_0']
print("encoder dense0 var shapes", jax.tree_map(jnp.shape, encoder_dense0.variables))