from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel


class UsesKernelMixin:
    """A mixin that provides an Agent Server kernel to the class."""

    def attach_kernel(self, kernel: "Kernel"):
        """Attach an Agent Server kernel to the class."""
        # We use object.__setattr__ because the mixin may be used on frozen dataclasses
        # and attachment must happen at runtime after initialization.
        object.__setattr__(self, "_internal_kernel", kernel)

    @property
    def kernel(self) -> "Kernel":
        """The kernel attached to the class."""
        return self._internal_kernel
