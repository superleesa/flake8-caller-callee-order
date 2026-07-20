from __future__ import annotations

from .models import Binding, BindingKind, Definition, Reference, ResolutionContext


class ReferenceResolver:
    def resolve_name(
        self,
        name: str,
        context: ResolutionContext,
    ) -> Binding | None:
        for frame in context:
            binding = frame.bindings.get(name)
            if binding is not None:
                return binding

        return None

    def resolve_reference(
        self,
        reference: Reference,
        context: ResolutionContext,
    ) -> Definition | None:
        if reference.base_name is None:
            binding = self.resolve_name(reference.name, context)
            if binding is not None and binding.kind == BindingKind.ORDERED:
                return binding.definition
            return None

        base_binding = self.resolve_name(reference.base_name, context)
        if (
            base_binding is not None
            and base_binding.kind == BindingKind.RECEIVER
            and base_binding.receiver_namespace is not None
        ):
            return base_binding.receiver_namespace.get(reference.name)

        return None
