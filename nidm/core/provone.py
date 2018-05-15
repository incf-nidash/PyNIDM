"""Python implementation of the ProvONE Model Specification

References:

ProvONE: http://vcvcomputing.com/provone/provone.html
"""

import logging

from prov.constants import PROV_N_MAP, PROV_ATTR_STARTTIME, PROV_ATTR_ENDTIME, \
	PROV_ATTR_TIME
from prov.model import ProvEntity, ProvAgent, ProvDocument, ProvAttribution, \
	PROV_REC_CLS, ProvActivity, _ensure_datetime, ProvAssociation, \
	ProvCommunication, ProvDerivation, ProvRelation, ProvGeneration
from .Constants import PROVONE_N_MAP, PROVONE_PROCESS, PROVONE_INPUTPORT, \
	PROVONE_OUTPUTPORT, PROVONE_DATA, PROVONE_DATALINK, PROVONE_SEQCTRLLINK, \
	PROVONE_USER, PROVONE_PROCESSEXEC, PROVONE_ATTR_PROCESS, PROVONE_ATTR_USER, \
	PROVONE_ATTRIBUTION, PROVONE_ATTR_PROCESSEXEC, PROVONE_ATTR_PLAN, \
	PROVONE_ASSOCIATION, PROVONE_ATTR_INFORMED, PROVONE_ATTR_INFORMANT, \
	PROVONE_COMMUNICATION, PROVONE_ATTR_GENERATED_DATA, PROVONE_ATTR_USED_DATA, \
	PROVONE_ATTR_GENERATION, PROVONE_ATTR_USAGE, PROVONE_DERIVATION, \
	PROVONE_ATTR_DATA, PROVONE_GENERATION, PROVONE_ATTR_INPUTPORT, \
	PROVONE_HASINPORT, PROVONE_ATTR_OUTPUTPORT, PROVONE_HASOUTPORT, \
	PROVONE_HASSUBPROCESS, PROVONE_ATTR_DATALINK, PROVONE_INPORTTODL, \
	PROVONE_OUTPORTTODL, PROVONE_DLTOOUTPORT, PROVONE_DLTOINPORT, \
	PROVONE_ATTR_SEQCTRLLINK, PROVONE_CLTODESTP, PROVONE_SOURCEPTOCL, \
	PROVONE_DATAONLINK, PROVONE_HASDEFAULTPARAM, PROVONE_USAGE, \
	PROVONE_ATTR_GENERATED_PROCESS, PROVONE_ATTR_USED_PROCESS

__author__ = 'Sanu Ann Abraham'
__email__ = 'sanuann@mit.edu'

logger = logging.getLogger(__name__)

# add ProvOne Notation mapping to Prov_N_MAP dict
PROV_N_MAP.update(PROVONE_N_MAP)


class ProvPlan(ProvEntity):
	"""
	ProvONE Plan element
	"""
	pass


class Process(ProvEntity):
	"""
	ProvONE Process element """

	_prov_type = PROVONE_PROCESS


class InputPort(ProvEntity):
	""" ProvONE Input Port element """

	_prov_type = PROVONE_INPUTPORT


class OutputPort(ProvEntity):
	""" ProvONE Output Port element"""

	_prov_type = PROVONE_OUTPUTPORT


class Data(ProvEntity):
	"""
	basic unit of information consumed or produced by a Process. Multiple Data items may be grouped into a Collection.
	"""
	_prov_type = PROVONE_DATA


class DataLink(ProvEntity):
	""" ProvONE DataLink Element """

	_prov_type = PROVONE_DATALINK


class SeqCtrlLink(ProvEntity):
	""" ProvONE SeqCtrlLink Element """

	_prov_type = PROVONE_SEQCTRLLINK


class User(ProvAgent):
	"""ProvONE User element."""

	_prov_type = PROVONE_USER


class ProcessExec(ProvActivity):

	def wasInformedBy(self, informant, attributes=None):
		"""
		Creates a new communication record for this activity.

		:param informant: The informing activity (relationship source).
		:param attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		self._bundle.communication(
			self, informant, other_attributes=attributes
		)
		return self

	_prov_type = PROVONE_PROCESSEXEC


class Attribution(ProvAttribution):
	"""ProvONE Attribution relationship."""

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_PROCESS, PROVONE_ATTR_USER)

	_prov_type = PROVONE_ATTRIBUTION


class Association(ProvAssociation):
	"""Provenance Association relationship."""
	FORMAL_ATTRIBUTES = (PROVONE_ATTR_PROCESSEXEC, PROVONE_ATTR_PROCESS,
						 PROVONE_ATTR_PLAN)

	_prov_type = PROVONE_ASSOCIATION


class Communication(ProvCommunication):
	"""Provenance Communication relationship."""

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_INFORMED, PROVONE_ATTR_INFORMANT)

	_prov_type = PROVONE_COMMUNICATION


class Derivation(ProvDerivation):
    """Provenance Derivation relationship."""

    FORMAL_ATTRIBUTES = (PROVONE_ATTR_GENERATED_DATA, PROVONE_ATTR_USED_DATA,
						 PROVONE_ATTR_PROCESSEXEC, PROVONE_ATTR_GENERATION,
						 PROVONE_ATTR_USAGE)

    _prov_type = PROVONE_DERIVATION


class Generation(ProvGeneration):
    """Provenance Generation relationship."""

    FORMAL_ATTRIBUTES = (PROVONE_ATTR_DATA, PROVONE_ATTR_PROCESSEXEC, PROV_ATTR_TIME)

    _prov_type = PROVONE_GENERATION


class HasInput(ProvRelation):
	"""ProvONE HasInput Port relationship."""

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_PROCESS, PROVONE_ATTR_INPUTPORT)

	_prov_type = PROVONE_HASINPORT


class HasOutput(ProvRelation):
	"""ProvONE HasOutput Port relationship."""

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_PROCESS, PROVONE_ATTR_OUTPUTPORT)

	_prov_type = PROVONE_HASOUTPORT


class HasSubProcess(ProvRelation):
	"""ProvONE Has SubProcess relationship."""

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_PROCESS, PROVONE_ATTR_PROCESS)

	_prov_type = PROVONE_HASSUBPROCESS


class InToDL(ProvRelation):
	""" ProvONE InPort to DL relationship """

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_INPUTPORT, PROVONE_ATTR_DATALINK)

	_prov_type = PROVONE_INPORTTODL


class OutToDL(ProvRelation):
	""" ProvONE Output port to DL relationship """

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_OUTPUTPORT, PROVONE_ATTR_DATALINK)

	_prov_type = PROVONE_OUTPORTTODL


class DLtoOutPort(ProvRelation):
	""" ProvONE DL to Output port relationship """

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_DATALINK, PROVONE_ATTR_OUTPUTPORT)

	_prov_type = PROVONE_DLTOOUTPORT


class DLtoInPort(ProvRelation):
	""" ProvONE DL to Input port relationship """

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_DATALINK, PROVONE_ATTR_INPUTPORT)

	_prov_type = PROVONE_DLTOINPORT


class CLtoDestP(ProvRelation):
	"""ProvONE CLtoDestP relationship."""

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_SEQCTRLLINK, PROVONE_ATTR_PROCESS)

	_prov_type = PROVONE_CLTODESTP


class SourcePtoCL(ProvRelation):
	"""ProvONE SourcePtoCL relationship."""

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_PROCESS, PROVONE_ATTR_SEQCTRLLINK)

	_prov_type = PROVONE_SOURCEPTOCL


class DataLinkage(ProvRelation):
	""" ProvONE dataOnLink relationship """

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_DATA, PROVONE_DATALINK, PROVONE_ATTR_PROCESS)

	_prov_type = PROVONE_DATAONLINK


class Parameterization(ProvRelation):
	""" ProvONE hasDefaultParam relationship. """

	FORMAL_ATTRIBUTES = (PROVONE_ATTR_INPUTPORT, PROVONE_ATTR_DATA)

	_prov_type = PROVONE_HASDEFAULTPARAM


class Workflow(Process):
	pass


#  Class mappings from PROVONE record type
PROV_REC_CLS.update({
	PROVONE_PROCESS: Process,
	PROVONE_PROCESSEXEC: ProcessExec,
	PROVONE_DATA: Data,
	PROVONE_ATTRIBUTION: Attribution,
	PROVONE_ASSOCIATION: Association,
	PROVONE_COMMUNICATION:  Communication,
	PROVONE_DERIVATION: Derivation,
	PROVONE_GENERATION: Generation,
	PROVONE_INPUTPORT: InputPort,
	PROVONE_HASINPORT: HasInput,
	PROVONE_OUTPUTPORT: OutputPort,
	PROVONE_HASOUTPORT: HasOutput,
	PROVONE_HASSUBPROCESS: HasSubProcess,
	PROVONE_DATALINK: DataLink,
	PROVONE_INPORTTODL: InToDL,
	PROVONE_SEQCTRLLINK: SeqCtrlLink,
	PROVONE_CLTODESTP: CLtoDestP,
	PROVONE_SOURCEPTOCL: SourcePtoCL,
	PROVONE_OUTPORTTODL: OutToDL,
	PROVONE_DLTOOUTPORT: DLtoOutPort,
	PROVONE_DLTOINPORT: DLtoInPort,
	PROVONE_DATAONLINK: DataLinkage,
	PROVONE_HASDEFAULTPARAM: Parameterization,

})


class ProvONEDocument(ProvDocument):
	""" ProvONE Document"""

	def __repr__(self):
		return '<ProvONEDocument>'

	def process(self, identifier, other_attributes=None):
		"""
		Creates a new process.

		:param identifier: Identifier for new process.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(PROVONE_PROCESS, identifier, None,
							   other_attributes)

	def user(self, identifier, other_attributes=None):
		"""
		Creates a new user.

		:param identifier: Identifier for new user.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(PROVONE_USER, identifier, None, other_attributes)

	def data(self, identifier, other_attributes=None):
		"""
		Creates a new data.

		:param identifier: Identifier for new data.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(PROVONE_DATA, identifier, None,
							   other_attributes)

	def attribution(self, process_spec, user, identifier=None,
					other_attributes=None):
		"""
		Creates a new attribution record between a process specification and an user.

		:param process_spec: ProcessSpecification or a string identifier for the process spec (relationship
			source).
		:param user: User or string identifier of the user involved in the
			attribution (relationship destination).
		:param identifier: Identifier for new attribution record.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_ATTRIBUTION, identifier, {
				PROVONE_ATTR_PROCESS: process_spec,
				PROVONE_ATTR_USER: user
			},
			other_attributes
		)

	def processExec(self, identifier, startTime=None, endTime=None,
					other_attributes=None):
		"""
		Creates a new process execution.

		:param identifier: Identifier for new process execution.
		:param startTime: Optional start time for the process execution (default:
		None).
			Either a :py:class:`datetime.datetime` object or a string that can be
			parsed by :py:func:`dateutil.parser`.
		:param endTime: Optional end time for the process execution (default: None).
			Either a :py:class:`datetime.datetime` object or a string that can be
			parsed by :py:func:`dateutil.parser`.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_PROCESSEXEC, identifier, {
				PROV_ATTR_STARTTIME: _ensure_datetime(startTime),
				PROV_ATTR_ENDTIME: _ensure_datetime(endTime)
			},
			other_attributes
		)

	def association(self, process_exec, process_spec=None, plan=None,
					identifier=None, other_attributes=None):
		"""
		Creates a new association record for a process execution.

		:param process_exec: Process Execution or a string identifier for the
			process execution.
		:param process_spec: Process Spec or string identifier of the process
			involved in the association (default: None).
		:param plan: Optionally extra entity to state qualified association through
			an internal plan (default: None).
		:param identifier: Identifier for new association record.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_ASSOCIATION, identifier, {
				PROVONE_ATTR_PROCESSEXEC: process_exec,
				PROVONE_ATTR_PROCESS: process_spec,
				PROVONE_ATTR_PLAN: plan
			},
			other_attributes
		)

	def derivation(self, generatedData, usedData, process_exec=None,
				   generation=None, usage=None,
				   identifier=None, other_attributes=None):
		"""
		Creates a new derivation record for a generated data from a used data.

		:param generatedData: Data or a string identifier for the generated
			data (relationship source).
		:param usedData: Data or a string identifier for the used data
			(relationship destination).
		:param process_exec: Process execution or string identifier of the
			processExec involved in the derivation (default: None).
		:param generation: Optionally extra activity to state qualified generation
			through a generation (default: None).
		:param usage: XXX (default: None).
		:param identifier: Identifier for new derivation record.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		attributes = {PROVONE_ATTR_GENERATED_DATA: generatedData,
					  PROVONE_ATTR_USED_DATA: usedData,
					  PROVONE_ATTR_PROCESSEXEC: process_exec,
					  PROVONE_ATTR_GENERATION: generation,
					  PROVONE_ATTR_USAGE: usage}
		return self.new_record(
			PROVONE_DERIVATION, identifier, attributes, other_attributes
		)

	def generation(self, data, process_exec=None, time=None, identifier=None,
				   other_attributes=None):
		"""
		Creates a new generation record for a data.

		:param data: Data or a string identifier for the data.
		:param process_exec: Process execution or string identifier of the
		process_exec involved in the generation (default: None).
		:param time: Optional time for the generation (default: None).
			Either a :py:class:`datetime.datetime` object or a string that can be
			parsed by :py:func:`dateutil.parser`.
		:param identifier: Identifier for new generation record.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_GENERATION, identifier, {
				PROVONE_ATTR_DATA: data,
				PROVONE_ATTR_PROCESSEXEC: process_exec,
				PROV_ATTR_TIME: _ensure_datetime(time)
			},
			other_attributes
		)

	def usage(self, process_exec, data=None, time=None, identifier=None,
			  other_attributes=None):
		"""
		Creates a new usage record for a process execution.

		:param process_exec: Process Execution or a string identifier for the
			processExec.
		:param data: Data or string identifier of the data involved in
			the usage relationship (default: None).
		:param time: Optional time for the usage (default: None).
			Either a :py:class:`datetime.datetime` object or a string that can be
			parsed by :py:func:`dateutil.parser`.
		:param identifier: Identifier for new usage record.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_USAGE, identifier, {
				PROVONE_ATTR_PROCESSEXEC: process_exec,
				PROVONE_ATTR_DATA: data,
				PROV_ATTR_TIME: _ensure_datetime(time)},
			other_attributes
		)

	def communication(self, informed, informant, identifier=None,
					  other_attributes=None):
		"""
		Creates a new communication record for a process exec.

		:param informed: The informed processExec (relationship destination).
		:param informant: The informing processExec (relationship source).
		:param identifier: Identifier for new communication record.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_COMMUNICATION, identifier, {
				PROVONE_ATTR_INFORMED: informed,
				PROVONE_ATTR_INFORMANT: informant
			},
			other_attributes
		)

	def input_port(self, identifier, other_attributes=None):
		"""
		Creates a new input port.

		:param identifier: Identifier for new input port.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(PROVONE_INPUTPORT, identifier, None,
							   other_attributes)

	def has_in_ports(self, process, in_ports, identifier=None,
					 other_attributes=None):
		"""
		Creates a new input port record for a process.

		:param process: Process or a string identifier for the
			process(relationship source).
		:param in_ports: Input Port or string identifier for the used input port (
			relationship destination).
		:param identifier: Identifier for new input port membership.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_HASINPORT, identifier, {
			PROVONE_ATTR_PROCESS: process,
			PROVONE_ATTR_INPUTPORT: in_ports,
			},
			other_attributes
		)

	def output_port(self, identifier, other_attributes=None):
		"""
		Creates a new output port.

		:param identifier: Identifier for new output port.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(PROVONE_OUTPUTPORT, identifier, None,
							   other_attributes)

	def has_out_ports(self, process, out_ports, identifier=None,
					  other_attributes=None):
		"""
		Creates a new input port record for a process.

		:param process: Process or a string identifier for the
			process(relationship source).
		:param out_ports: Output Port or string identifier for the used output
		port (relationship destination).
		:param identifier: Identifier for new output port membership.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_HASOUTPORT, identifier, {
			PROVONE_ATTR_PROCESS: process,
			PROVONE_ATTR_OUTPUTPORT: out_ports,
			},
			other_attributes
		)

	def has_sub_process(self, generated_process, used_process, identifier=None,
						other_attributes=None ):
		"""
				Creates a new has-sub-process record for a generated process from a
				used process.

				:param generated_process: Process or a string identifier for the
				generated process (relationship source).
				:param used_process: Process or a string identifier for the used
				process (relationship destination).
				:param identifier: Identifier for new has-sub-process record.
				:param other_attributes: Optional other attributes as a dictionary or list
					of tuples to be added to the record optionally (default: None).
				"""
		attributes = {PROVONE_ATTR_GENERATED_PROCESS: generated_process,
					  PROVONE_ATTR_USED_PROCESS: used_process}
		return self.new_record(
			PROVONE_HASSUBPROCESS, identifier, attributes, other_attributes
		)

	def dataLink(self, identifier, other_attributes=None):
		"""
		Creates a new data link.

		:param identifier: Identifier for new data link.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(PROVONE_DATALINK, identifier, None,
							   other_attributes)

	def inPortToDL(self, in_port, dt_link, identifier=None,
					  other_attributes=None):
		"""

		:param in_port: Input port or a string identifier for the
			in_port(relationship source).
		:param dt_link: Data Link or string identifier for the used data link (
			relationship destination).
		:param identifier: Identifier for new data link membership.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(
			PROVONE_INPORTTODL, identifier, {
				PROVONE_ATTR_INPUTPORT: in_port,
				PROVONE_ATTR_DATALINK: dt_link,
			},
			other_attributes
		)

	def outPortToDL(self, out_port, dt_link, identifier=None,
					  other_attributes=None):
		"""

		:param out_port: Output port or a string identifier for the
			out_port(relationship source).
		:param dt_link: Data Link or string identifier for the used data link (
			relationship destination).
		:param identifier: Identifier for new output-data link membership.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(
			PROVONE_OUTPORTTODL, identifier, {
				PROVONE_ATTR_OUTPUTPORT: out_port,
				PROVONE_ATTR_DATALINK: dt_link,
			},
			other_attributes
		)

	def DLToOutPort(self, dt_link, out_port, identifier=None,
					  other_attributes=None):
		"""

		:param dt_link: Data Link or string identifier for the used data link (
			relationship source).
		:param out_port: Output port or a string identifier for the
			out_port(relationship destination).
		:param identifier: Identifier for new data link-output membership.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(
			PROVONE_DLTOOUTPORT, identifier, {
				PROVONE_ATTR_DATALINK: dt_link,
				PROVONE_ATTR_OUTPUTPORT: out_port,
			},
			other_attributes
		)

	def DLToInPort(self, dt_link, in_port, identifier=None,
					  other_attributes=None):
		"""

		:param dt_link: Data Link or string identifier for the used data link (
			relationship source).
		:param in_port: Input port or a string identifier for the in_port (
			relationship destination).
		:param identifier: Identifier for new data link-output membership.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(
			PROVONE_DLTOINPORT, identifier, {
				PROVONE_ATTR_DATALINK: dt_link,
				PROVONE_ATTR_INPUTPORT: in_port,
			},
			other_attributes
		)

	def seqCtrlLink(self, identifier, other_attributes=None):
		"""
		Creates a new seq ctrl link.

		:param identifier: Identifier for new seq ctrl link.
		:param other_attributes: Optional other attributes as a dictionary or list
			of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(PROVONE_SEQCTRLLINK, identifier, None,
							   other_attributes)

	def control_link_to_process(self, used_cntrl_link, used_process,
								identifier=None, other_attributes=None):
		"""

		:param used_cntrl_link: Control Link or a string identifier for the used
		control link (relationship source).
		:param used_process: Data Link or string identifier for the used process
		(relationship destination).
		:param identifier: Identifier for new control link to process relation.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(
			PROVONE_CLTODESTP, identifier, {
				PROVONE_ATTR_SEQCTRLLINK: used_cntrl_link,
				PROVONE_ATTR_PROCESS: used_process,
			},
			other_attributes)

	def process_to_control_link(self, used_process, used_cntrl_link,
								identifier=None, other_attributes=None):
		"""

		:param used_process: Process or string identifier for the used process
		(relationship source).
		:param used_cntrl_link: Control Link or a string identifier for the used
		control link (relationship destination).
		:param identifier: Identifier for new process to control link relation.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(
			PROVONE_SOURCEPTOCL, identifier, {
				PROVONE_ATTR_PROCESS: used_process,
				PROVONE_ATTR_SEQCTRLLINK: used_cntrl_link,
			},
			other_attributes)

	def dataOnLink(self, data_item, dl_link, relatedProcess=None, identifier=None,
				   other_attributes=None):
		"""

		:param data_item: Data or string identifier for the associated data (
		relationship source).
		:param dl_link: Data link or string identifier for the data link (
		relationship destination).
		:param process: Process or string identifier of the data link (default=None)
		:param identifier: Identifier for new data-on-link relation.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).

		"""
		return self.new_record(
			PROVONE_DATAONLINK, identifier, {
				PROVONE_ATTR_DATA: data_item,
				PROVONE_ATTR_DATALINK: dl_link,
				PROVONE_ATTR_PROCESS: relatedProcess,
			},
			other_attributes)

	def parameterization(self, in_port, data_item, identifier=None,
						 other_attributes=None):
		"""

		:param in_port: InputPort or string identifier for the associated in port (
		relationship source).
		:param data_item: Data item or string identifier for the associated
		default parameter (relationship destination).
		:param identifier: Identifier for new default parameter relation.
		:param other_attributes: Optional other attributes as a dictionary or
			list of tuples to be added to the record optionally (default: None).
		"""
		return self.new_record(
			PROVONE_HASDEFAULTPARAM, identifier, {
				PROVONE_ATTR_INPUTPORT: in_port,
				PROVONE_ATTR_DATA: data_item,
			},
			other_attributes)

	# Aliases
	wasAttributedTo = attribution
	wasAssociatedWith = association
	wasDerivedFrom = derivation
	wasGeneratedBy = generation
	wasInformedBy = communication
	used = usage
	hasInPort = has_in_ports
	hasOutPort = has_out_ports
	hasSubProcess = has_sub_process
	CLtoDestP = control_link_to_process
	sourcePToCL = process_to_control_link
	hasDefaultParam = parameterization
