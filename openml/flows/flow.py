from collections import OrderedDict
import os
from typing import Dict, List, Union  # noqa: F401

import xmltodict

from ..extensions import get_extension_by_flow
from ..utils import extract_xml_tags, _tag_entity

import openml.config


class OpenMLFlow(object):
    """OpenML Flow. Stores machine learning models.

    Flows should not be generated manually, but by the function
    :meth:`openml.flows.create_flow_from_model`. Using this helper function
    ensures that all relevant fields are filled in.

    Implements https://github.com/openml/website/blob/master/openml_OS/ \
        views/pages/api_new/v1/xsd/openml.implementation.upload.xsd.

    Parameters
    ----------
    name : str
        Name of the flow. Is used together with the attribute
        `external_version` as a unique identifier of the flow.
    description : str
        Human-readable description of the flow (free text).
    model : object
        ML model which is described by this flow.
    components : OrderedDict
        Mapping from component identifier to an OpenMLFlow object. Components
        are usually subfunctions of an algorithm (e.g. kernels), base learners
        in ensemble algorithms (decision tree in adaboost) or building blocks
        of a machine learning pipeline. Components are modeled as independent
        flows and can be shared between flows (different pipelines can use
        the same components).
    parameters : OrderedDict
        Mapping from parameter name to the parameter default value. The
        parameter default value must be of type `str`, so that the respective
        toolbox plugin can take care of casting the parameter default value to
        the correct type.
    parameters_meta_info : OrderedDict
        Mapping from parameter name to `dict`. Stores additional information
        for each parameter. Required keys are `data_type` and `description`.
    external_version : str
        Version number of the software the flow is implemented in. Is used
        together with the attribute `name` as a uniquer identifier of the flow.
    tags : list
        List of tags. Created on the server by other API calls.
    language : str
        Natural language the flow is described in (not the programming
        language).
    dependencies : str
        A list of dependencies necessary to run the flow. This field should
        contain all libraries the flow depends on. To allow reproducibility
        it should also specify the exact version numbers.
    class_name : str
        The development language name of the class which is described by this
        flow.
    custom_name : str
        Custom name of the flow given by the owner.
    binary_url : str, optional
        Url from which the binary can be downloaded. Added by the server.
        Ignored when uploaded manually. Will not be used by the python API
        because binaries aren't compatible across machines.
    binary_format : str, optional
        Format in which the binary code was uploaded. Will not be used by the
        python API because binaries aren't compatible across machines.
    binary_md5 : str, optional
        MD5 checksum to check if the binary code was correctly downloaded. Will
        not be used by the python API because binaries aren't compatible across
        machines.
    uploader : str, optional
        OpenML user ID of the uploader. Filled in by the server.
    upload_date : str, optional
        Date the flow was uploaded. Filled in by the server.
    flow_id : int, optional
        Flow ID. Assigned by the server.
    version : str, optional
        OpenML version of the flow. Assigned by the server.
    """

    def __init__(self, name, description, model, components, parameters,
                 parameters_meta_info, external_version, tags, language,
                 dependencies, class_name=None, custom_name=None,
                 binary_url=None, binary_format=None,
                 binary_md5=None, uploader=None, upload_date=None,
                 flow_id=None, version=None):
        self.name = name
        self.description = description
        self.model = model

        for variable, variable_name in [
                [components, 'components'],
                [parameters, 'parameters'],
                [parameters_meta_info, 'parameters_meta_info']]:
            if not isinstance(variable, OrderedDict):
                raise TypeError('%s must be of type OrderedDict, '
                                'but is %s.' % (variable_name, type(variable)))

        self.components = components
        self.parameters = parameters
        self.parameters_meta_info = parameters_meta_info
        self.class_name = class_name

        keys_parameters = set(parameters.keys())
        keys_parameters_meta_info = set(parameters_meta_info.keys())
        if len(keys_parameters.difference(keys_parameters_meta_info)) > 0:
            raise ValueError('Parameter %s only in parameters, but not in '
                             'parameters_meta_info.' %
                             str(keys_parameters.difference(
                                 keys_parameters_meta_info)))
        if len(keys_parameters_meta_info.difference(keys_parameters)) > 0:
            raise ValueError('Parameter %s only in parameters_meta_info, '
                             'but not in parameters.' %
                             str(keys_parameters_meta_info.difference(
                                 keys_parameters)))

        self.external_version = external_version
        self.uploader = uploader

        self.custom_name = custom_name
        self.tags = tags if tags is not None else []
        self.binary_url = binary_url
        self.binary_format = binary_format
        self.binary_md5 = binary_md5
        self.version = version
        self.upload_date = upload_date
        self.language = language
        self.dependencies = dependencies
        self.flow_id = flow_id

        self._extension = get_extension_by_flow(self)

    @property
    def extension(self):
        if self._extension is not None:
            return self._extension
        else:
            raise RuntimeError("No extension could be found for flow {}: {}"
                               .format(self.flow_id, self.name))

    def __str__(self):
        header = "OpenML Flow"
        header = '{}\n{}\n'.format(header, '=' * len(header))

        base_url = "{}".format(openml.config.server[:-len('api/v1/xml')])
        fields = {"Flow Name": self.name,
                  "Flow Description": self.description,
                  "Dependencies": self.dependencies}
        if self.flow_id is not None:
            if self.version is not None:
                fields["Flow ID"] = "{} (version {})".format(self.flow_id, self.version)
            else:
                fields["Flow ID"] = self.flow_id
            fields["Flow URL"] = "{}f/{}".format(base_url, self.flow_id)
        if self.upload_date is not None:
            fields["Upload Date"] = self.upload_date.replace('T', ' ')
        if self.binary_url is not None:
            fields["Binary URL"] = self.binary_url

        # determines the order in which the information will be printed
        order = ["Flow ID", "Flow URL", "Flow Name", "Flow Description", "Binary URL",
                 "Upload Date", "Dependencies"]
        fields = [(key, fields[key]) for key in order if key in fields]

        longest_field_name_length = max(len(name) for name, value in fields)
        field_line_format = "{{:.<{}}}: {{}}".format(longest_field_name_length)
        body = '\n'.join(field_line_format.format(name, value) for name, value in fields)
        return header + body

    def _to_xml(self) -> str:
        """Generate xml representation of self for upload to server.

        Returns
        -------
        str
            Flow represented as XML string.
        """
        flow_dict = self._to_dict()
        flow_xml = xmltodict.unparse(flow_dict, pretty=True)

        # A flow may not be uploaded with the xml encoding specification:
        # <?xml version="1.0" encoding="utf-8"?>
        flow_xml = flow_xml.split('\n', 1)[-1]
        return flow_xml

    def _to_dict(self) -> dict:
        """ Helper function used by _to_xml and itself.

        Creates a dictionary representation of self which can be serialized
        to xml by the function _to_xml. Since a flow can contain subflows
        (components) this helper function calls itself recursively to also
        serialize these flows to dictionaries.

        Uses OrderedDict to ensure consistent ordering when converting to xml.
        The return value (OrderedDict) will be used to create the upload xml
        file. The xml file must have the tags in exactly the order given in the
        xsd schema of a flow (see class docstring).

        Returns
        -------
        OrderedDict
            Flow represented as OrderedDict.

        """
        flow_container = OrderedDict()  # type: 'OrderedDict[str, OrderedDict]'
        flow_dict = OrderedDict([('@xmlns:oml', 'http://openml.org/openml')])  # type: 'OrderedDict[str, Union[List, str]]'  # noqa E501
        flow_container['oml:flow'] = flow_dict
        _add_if_nonempty(flow_dict, 'oml:id', self.flow_id)

        for required in ["name", "external_version"]:
            if getattr(self, required) is None:
                raise ValueError("self.{} is required but None".format(
                    required))
        for attribute in ["uploader", "name", "custom_name", "class_name",
                          "version", "external_version", "description",
                          "upload_date", "language", "dependencies"]:
            _add_if_nonempty(flow_dict, 'oml:{}'.format(attribute),
                             getattr(self, attribute))

        flow_parameters = []
        for key in self.parameters:
            param_dict = OrderedDict()  # type: 'OrderedDict[str, str]'
            param_dict['oml:name'] = key
            meta_info = self.parameters_meta_info[key]

            _add_if_nonempty(param_dict, 'oml:data_type',
                             meta_info['data_type'])
            param_dict['oml:default_value'] = self.parameters[key]
            _add_if_nonempty(param_dict, 'oml:description',
                             meta_info['description'])

            for key_, value in param_dict.items():
                if key_ is not None and not isinstance(key_, str):
                    raise ValueError('Parameter name %s cannot be serialized '
                                     'because it is of type %s. Only strings '
                                     'can be serialized.' % (key_, type(key_)))
                if value is not None and not isinstance(value, str):
                    raise ValueError('Parameter value %s cannot be serialized '
                                     'because it is of type %s. Only strings '
                                     'can be serialized.'
                                     % (value, type(value)))

            flow_parameters.append(param_dict)

        flow_dict['oml:parameter'] = flow_parameters

        components = []
        for key in self.components:
            component_dict = OrderedDict()  # type: 'OrderedDict[str, Dict]'
            component_dict['oml:identifier'] = key
            component_dict['oml:flow'] = self.components[key]._to_dict()['oml:flow']

            for key_ in component_dict:
                # We only need to check if the key is a string, because the
                # value is a flow. The flow itself is valid by recursion
                if key_ is not None and not isinstance(key_, str):
                    raise ValueError('Parameter name %s cannot be serialized '
                                     'because it is of type %s. Only strings '
                                     'can be serialized.' % (key_, type(key_)))

            components.append(component_dict)

        flow_dict['oml:component'] = components
        flow_dict['oml:tag'] = self.tags
        for attribute in ["binary_url", "binary_format", "binary_md5"]:
            _add_if_nonempty(flow_dict, 'oml:{}'.format(attribute),
                             getattr(self, attribute))

        return flow_container

    @classmethod
    def _from_dict(cls, xml_dict):
        """Create a flow from an xml description.

        Calls itself recursively to create :class:`OpenMLFlow` objects of
        subflows (components).

        Parameters
        ----------
        xml_dict : dict
            Dictionary representation of the flow as created by _to_dict()

        Returns
        -------
            OpenMLFlow

        """
        arguments = OrderedDict()
        dic = xml_dict["oml:flow"]

        # Mandatory parts in the xml file
        for key in ['name', 'external_version']:
            arguments[key] = dic["oml:" + key]

        # non-mandatory parts in the xml file
        for key in ['uploader', 'description', 'upload_date', 'language',
                    'dependencies', 'version', 'binary_url', 'binary_format',
                    'binary_md5', 'class_name', 'custom_name']:
            arguments[key] = dic.get("oml:" + key)

        # has to be converted to an int if present and cannot parsed in the
        # two loops above
        arguments['flow_id'] = (int(dic['oml:id']) if dic.get("oml:id")
                                is not None else None)

        # Now parse parts of a flow which can occur multiple times like
        # parameters, components (subflows) and tags. These can't be tackled
        # in the loops above because xmltodict returns a dict if such an
        # entity occurs once, and a list if it occurs multiple times.
        # Furthermore, they must be treated differently, for example
        # for components this method is called recursively and
        # for parameters the actual information is split into two dictionaries
        # for easier access in python.

        parameters = OrderedDict()
        parameters_meta_info = OrderedDict()
        if 'oml:parameter' in dic:
            # In case of a single parameter, xmltodict returns a dictionary,
            # otherwise a list.
            oml_parameters = extract_xml_tags('oml:parameter', dic,
                                              allow_none=False)

            for oml_parameter in oml_parameters:
                parameter_name = oml_parameter['oml:name']
                default_value = oml_parameter['oml:default_value']
                parameters[parameter_name] = default_value

                meta_info = OrderedDict()
                meta_info['description'] = oml_parameter.get('oml:description')
                meta_info['data_type'] = oml_parameter.get('oml:data_type')
                parameters_meta_info[parameter_name] = meta_info
        arguments['parameters'] = parameters
        arguments['parameters_meta_info'] = parameters_meta_info

        components = OrderedDict()
        if 'oml:component' in dic:
            # In case of a single component xmltodict returns a dict,
            # otherwise a list.
            oml_components = extract_xml_tags('oml:component', dic,
                                              allow_none=False)

            for component in oml_components:
                flow = OpenMLFlow._from_dict(component)
                components[component['oml:identifier']] = flow
        arguments['components'] = components
        arguments['tags'] = extract_xml_tags('oml:tag', dic)

        arguments['model'] = None
        flow = cls(**arguments)

        return flow

    def to_filesystem(self, output_directory: str) -> None:
        os.makedirs(output_directory, exist_ok=True)
        if 'flow.xml' in os.listdir(output_directory):
            raise ValueError('Output directory already contains a flow.xml file.')

        run_xml = self._to_xml()
        with open(os.path.join(output_directory, 'flow.xml'), 'w') as f:
            f.write(run_xml)

    @classmethod
    def from_filesystem(cls, input_directory) -> 'OpenMLFlow':
        with open(os.path.join(input_directory, 'flow.xml'), 'r') as f:
            xml_string = f.read()
        return OpenMLFlow._from_dict(xmltodict.parse(xml_string))

    def publish(self, raise_error_if_exists: bool = False) -> 'OpenMLFlow':
        """ Publish this flow to OpenML server.

        Raises a PyOpenMLError if the flow exists on the server, but
        `self.flow_id` does not match the server known flow id.

        Parameters
        ----------
        raise_error_if_exists : bool, optional (default=False)
            If True, raise PyOpenMLError if the flow exists on the server.
            If False, update the local flow to match the server flow.

        Returns
        -------
        self : OpenMLFlow

        """
        # Import at top not possible because of cyclic dependencies. In
        # particular, flow.py tries to import functions.py in order to call
        # get_flow(), while functions.py tries to import flow.py in order to
        # instantiate an OpenMLFlow.
        import openml.flows.functions

        flow_id = openml.flows.functions.flow_exists(self.name, self.external_version)
        if not flow_id:
            if self.flow_id:
                raise openml.exceptions.PyOpenMLError("Flow does not exist on the server, "
                                                      "but 'flow.flow_id' is not None.")
            xml_description = self._to_xml()
            file_elements = {'description': xml_description}
            return_value = openml._api_calls._perform_api_call(
                "flow/",
                'post',
                file_elements=file_elements,
            )
            server_response = xmltodict.parse(return_value)
            flow_id = int(server_response['oml:upload_flow']['oml:id'])
        elif raise_error_if_exists:
            error_message = "This OpenMLFlow already exists with id: {}.".format(flow_id)
            raise openml.exceptions.PyOpenMLError(error_message)
        elif self.flow_id is not None and self.flow_id != flow_id:
            raise openml.exceptions.PyOpenMLError("Local flow_id does not match server flow_id: "
                                                  "'{}' vs '{}'".format(self.flow_id, flow_id))

        flow = openml.flows.functions.get_flow(flow_id)
        _copy_server_fields(flow, self)
        try:
            openml.flows.functions.assert_flows_equal(
                self, flow, flow.upload_date, ignore_parameter_values=True
            )
        except ValueError as e:
            message = e.args[0]
            raise ValueError("Flow was not stored correctly on the server. "
                             "New flow ID is %d. Please check manually and "
                             "remove the flow if necessary! Error is:\n'%s'" %
                             (flow_id, message))
        return self

    def get_structure(self, key_item: str) -> Dict[str, List[str]]:
        """
        Returns for each sub-component of the flow the path of identifiers
        that should be traversed to reach this component. The resulting dict
        maps a key (identifying a flow by either its id, name or fullname) to
        the parameter prefix.

        Parameters
        ----------
        key_item: str
            The flow attribute that will be used to identify flows in the
            structure. Allowed values {flow_id, name}

        Returns
        -------
        dict[str, List[str]]
            The flow structure
        """
        if key_item not in ['flow_id', 'name']:
            raise ValueError('key_item should be in {flow_id, name}')
        structure = dict()
        for key, sub_flow in self.components.items():
            sub_structure = sub_flow.get_structure(key_item)
            for flow_name, flow_sub_structure in sub_structure.items():
                structure[flow_name] = [key] + flow_sub_structure
        structure[getattr(self, key_item)] = []
        return structure

    def get_subflow(self, structure):
        """
        Returns a subflow from the tree of dependencies.

        Parameters
        ----------
        structure: list[str]
            A list of strings, indicating the location of the subflow

        Returns
        -------
        OpenMLFlow
            The OpenMLFlow that corresponds to the structure
        """
        # make a copy of structure, as we don't want to change it in the
        # outer scope
        structure = list(structure)
        if len(structure) < 1:
            raise ValueError('Please provide a structure list of size >= 1')
        sub_identifier = structure[0]
        if sub_identifier not in self.components:
            raise ValueError('Flow %s does not contain component with '
                             'identifier %s' % (self.name, sub_identifier))
        if len(structure) == 1:
            return self.components[sub_identifier]
        else:
            structure.pop(0)
            return self.components[sub_identifier].get_subflow(structure)

    def push_tag(self, tag):
        """Annotates this flow with a tag on the server.

        Parameters
        ----------
        tag : str
            Tag to attach to the flow.
        """
        _tag_entity('flow', self.flow_id, tag)

    def remove_tag(self, tag):
        """Removes a tag from this flow on the server.

        Parameters
        ----------
        tag : str
            Tag to attach to the flow.
        """
        _tag_entity('flow', self.flow_id, tag, untag=True)


def _copy_server_fields(source_flow, target_flow):
    fields_added_by_the_server = ['flow_id', 'uploader', 'version',
                                  'upload_date']
    for field in fields_added_by_the_server:
        setattr(target_flow, field, getattr(source_flow, field))

    for name, component in source_flow.components.items():
        assert name in target_flow.components
        _copy_server_fields(component, target_flow.components[name])


def _add_if_nonempty(dic, key, value):
    if value is not None:
        dic[key] = value
