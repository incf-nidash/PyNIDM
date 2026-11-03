"""
PersonalDataElement -- a DataElement for personal / demographic data
(age, sex, handedness, diagnosis, etc.).

Inherits from ``DataElement`` at the Python level and from
``nidm:DataElement`` at the RDF / OWL level (the schema declares
``is_a: DataElement`` on ``PersonalDataElement`` and we use
``rdfs:subClassOf`` semantics for that relationship).  Per-instance,
PersonalDataElement emits ``rdf:type nidm:PersonalDataElement`` and
``rdf:type prov:Entity`` -- NOT ``rdf:type nidm:DataElement`` (the
subClassOf relation is a schema-level assertion, not an instance
type).

Constructor signature, field set, and parent-registration behavior
are identical to ``DataElement``.  The only difference is the
``pydantic_class`` (and therefore the ``class_uri`` /
``additional_rdf_types`` emitted at construction time).
"""
from __future__ import annotations
from .data_element import DataElement
from ..generated import nidm_schema_pydantic as gen


class PersonalDataElement(DataElement):
    """
    A DataElement carrying personal / demographic metadata.

    Examples
    --------
    >>> from nidm.linkml.experiment import Project, PersonalDataElement
    >>> p = Project()
    >>> pde = PersonalDataElement(p, label="age", value_type="xsd:integer")
    >>> p.get_dataelements() == [pde]
    True
    """

    pydantic_class = gen.PersonalDataElement


__all__ = ["PersonalDataElement"]
