from agent_server_types_v2.kernel import Kernel


class UsesKernelMixin:
    def attach_kernel(self, kernel: Kernel):
        self._internal_kernel = kernel
    
    @property
    def kernel(self) -> Kernel:
        return self._internal_kernel
