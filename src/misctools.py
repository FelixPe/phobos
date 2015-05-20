#!/usr/bin/python

"""
.. module:: phobos.misctool
    :platform: Unix, Windows, Mac
    :synopsis: TODO: INSERT TEXT HERE

.. moduleauthor:: Kai von Szadowski

Copyright 2014, University of Bremen & DFKI GmbH Robotics Innovation Center

This file is part of Phobos, a Blender Add-On to edit robot models.

Phobos is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License
as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.

Phobos is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Phobos.  If not, see <http://www.gnu.org/licenses/>.

File misctools.py

Created on 6 Jan 2014

"""

import bpy
import math
from datetime import datetime as dt

import mathutils
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatVectorProperty, EnumProperty, FloatProperty
from . import robotupdate
from . import materials
from . import utility
from . import defs
from . import inertia
from . import robotdictionary
from . import validator
from phobos.logging import *
import yaml


def register():
    """
    This function registers this module.
    At the moment it does nothing.

    :return: Nothing

    """
    print("Registering misctools...")


def unregister():
    """
    This function unregisters this module.
    At the moment it does nothing.

    :return: Nothing

    """

    print("Unregistering misctools...")

class ToggleNamespaces(Operator):
    """ToggleNamespacesOperater

    """
    bl_idname = "object.phobos_toggle_namespaces"
    bl_label = "Toggles the use of namespaces for the selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    complete = BoolProperty(
        name="Converting complete robot",
        default=False
    )

    def execute(self, context):
        startLog(self)
        objlist = context.selected_objects
        if self.complete:
            roots = list(set([utility.getRoot(obj) for obj in context.selected_objects]))
            if None in roots:
                roots.remove(None)
            objlist = [elem for sublist in [utility.getChildren(root) for root in roots] for elem in sublist]
        objnames = [o.name for o in bpy.data.objects]
        for obj in objlist:
            if "::" in obj.name:
                if utility.namesAreExplicit({obj.name.split("::")[-1]}, objnames):
                    utility.removeNamespace(obj)
                else:
                    log("Cannot remove namespace from " + obj.name + ". Name wouldn't be explicit", "ERROR")
            else:
                utility.addNamespace(obj)
        endLog()
        return {'FINISHED'}

class SelectError(Operator):
    """SelectErrorOperator

    """
    bl_idname = "object.phobos_select_error"
    bl_label = "Selects an object with check errors"
    bl_options = {'REGISTER', 'UNDO'}

    errorObj = EnumProperty(
        name="Error containing objects",
        items=defs.generateCheckMessages,
        description="The objects containing errors.")

    def execute(self, context):
        startLog(self)
        utility.selectByName(self.errorObj)
        for message in defs.checkMessages[self.errorObj]:
            log(message, 'INFO')
        endLog()

        return {'FINISHED'}

class CheckDict(Operator):
    """CheckDictOperator

    """

    bl_idname = "object.phobos_check_dict"
    bl_label = "Checks the robotdictionary"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        """Executes the operator and unifies the selected objects meshes

        :param context: The blender context to work with
        :return: Blender result
        """
        startLog(self)
        messages = {}
        dic = robotdictionary.buildRobotDictionary()
        validator.check_dict(dic, defs.dictConstraints, messages)
        defs.checkMessages = messages if len(list(messages.keys())) > 0 else {"NoObject": []}
        for entry in messages:
            log("Errors in object " + entry + ":", 'INFO')
            for error in messages[entry]:
                log(error, 'INFO')
        endLog()
        return {'FINISHED'}


class ShareMesh(Operator):
    """ShareMeshOperator
    This operator takes the data block of the active element and sets it for all other selected elements.
    It also tags the objects with an visual/export/unifiedMesh custom property telling the meshes name.

    """

    bl_idname = "object.phobos_share_mesh"
    bl_label = "Unifies the selected objects meshes by setting all meshes to the active objects one"
    bl_options = {'REGISTER', 'UNDO'}

    meshName = StringProperty (
            name = "shared Meshes Name",
            default = '',
            description = "The shared meshes name")

    def execute(self, context):
        """Executes the operator and unifies the selected objects meshes

        :param context: The blender context to work with
        :return: Blender result
        """
        startLog(self)
        objects = context.selected_objects
        source = context.active_object
        sMProp = 'geometry/'+defs.reservedProperties['SHAREDMESH']
        newName = source.name if self.meshName == "" else self.meshName
        log(source.name, "INFO")
        for obj in objects:
            if 'phobostype' in obj and obj.phobostype in ("visual", "collision") and obj != source:
                log("Setting data for: " + obj.name, "INFO")
                obj.data = source.data
                obj[sMProp] = newName
        if sMProp in source: del obj[sMProp]
        source['geometry/filename'] = newName
        log("Successfully shared the meshes for selected objects!" ,"INFO")
        endLog()
        return {'FINISHED'}

class UndoShareMesh(Operator):
    """UndoShareMeshOperator
    This operator undos the mesh sharing of all selected objects by delinking all objects mesh data and deleting the
    geometry/sharedMeshFile tags.
    """

    bl_idname = "object.phobos_undo_share_mesh"
    bl_label = "Undos the shared mesh operation on all selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        """Executes the operator and undos all mesh sharing

        :param context: The blender context to work with
        :return: Blender result.
        """
        bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)
        sMProp = 'geometry/'+defs.reservedProperties['SHAREDMESH']
        for obj in context.selected_objects:
            if sMProp in obj:
                del obj[sMProp]
            if 'geometry/filename' in obj:
                del obj['geometry/filename']
        return {'FINISHED'}

class CalculateMassOperator(Operator):
    """CalculateMassOperator

    """
    bl_idname = "object.phobos_calculate_mass"
    bl_label = "Display mass of the selected objects in a pop-up window."

    def execute(self, context):
        startLog(self)
        mass = utility.calculateSum(bpy.context.selected_objects, 'mass')
        log("The calculated mass is: " + str(mass), "INFO")
        endLog()
        return {'FINISHED'}


class SortObjectsToLayersOperator(Operator):
    """SortObjectsToLayersOperator

    """
    bl_idname = "object.phobos_sort_objects_to_layers"
    bl_label = "Sorts all selected objects to their according layers"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        startLog(self)
        for obj in context.selected_objects:
            try:
                phobosType = obj.phobostype
                if phobosType != 'controller' and phobosType != 'undefined':
                    layers = 20 * [False]
                    layers[defs.layerTypes[phobosType]] = True
                    obj.layers = layers
                if phobosType == 'undefined':
                    log("The phobostype of the object '" + obj.name + "' is undefined")
            except AttributeError:
                log("The object '" + obj.name + "' has no phobostype", "ERROR")  # Handle this as error or warning?
        endLog()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) > 0:
            return True
        else:
            return False


class AddChainOperator(Operator):
    """AddChainOperator

    """
    bl_idname = "object.phobos_add_chain"
    bl_label = "Adds a chain between two selected objects."
    bl_options = {'REGISTER', 'UNDO'}

    chainname = StringProperty(
        name='chainname',
        default='new_chain',
        description='name of the chain to be created')

    def execute(self, context):
        endobj = context.active_object
        for obj in context.selected_objects:
            if obj is not context.active_object:
                startobj = obj
                break
        if not 'startChain' in startobj:
            startobj['startChain'] = [self.chainname]
        else:
            namelist = startobj['startChain']
            if self.chainname not in namelist:
                namelist.append(self.chainname)
            startobj['startChain'] = namelist
        if not 'endChain' in endobj:
            endobj['endChain'] = [self.chainname]
        else:
            namelist = endobj['endChain']
            if self.chainname not in namelist:
                namelist.append(self.chainname)
            endobj['endChain'] = namelist
        return {'FINISHED'}


class SetMassOperator(Operator):
    """SetMassOperator

    """
    bl_idname = "object.phobos_set_mass"
    bl_label = "Sets the mass of the selected object(s)."
    bl_options = {'REGISTER', 'UNDO'}

    mass = FloatProperty(
        name='mass',
        default=0.001,
        description='mass (of active object) in kg')

    userbmass = BoolProperty(
        name='use rigid body mass',
        default=False,
        description='If True, mass entry from rigid body data is used.')

    @classmethod
    def poll(cls, context):
        for obj in context.selected_objects:
            if obj.phobostype in ['visual', 'collision', 'inertial']:
                return True
        return False

    def invoke(self, context, event):
        if 'mass' in context.active_object:
            self.mass = context.active_object['mass']
        return self.execute(context)

    def execute(self, context):
        startLog(self)
        for obj in bpy.context.selected_objects:
            if obj.phobostype in ['visual', 'collision', 'inertial']:
                try:
                    oldmass = obj['mass']
                except KeyError:
                    log("The object '" + obj.name + "' has no mass")
                    oldmass = None
                if self.userbmass:
                    try:
                        obj['mass'] = obj.rigid_body.mass
                    except AttributeError:
                        obj['mass'] = 0.001
                        # print("### Error: object has no rigid body properties.")
                        log("The object '" + obj.name + "' has no rigid body properties. Set mass to 0.001", "ERROR")
                else:
                    obj['mass'] = self.mass
                if obj['mass'] != oldmass:
                    t = dt.now()
                    obj['masschanged'] = t.isoformat()
        endLog()
        return {'FINISHED'}


class SyncMassesOperator(Operator):
    """SyncMassesOperator

    """
    bl_idname = "object.phobos_sync_masses"
    bl_label = "Synchronize masses among the selected object(s)."
    bl_options = {'REGISTER', 'UNDO'}

    synctype = EnumProperty(
        items=(("vtc", "visual to collision", "visual to collision"),
               ("ctv", "collision to visual", "collision to visual"),
               ("lto", "latest to oldest", "latest to oldest")),
        name="synctype",
        default="vtc",
        description="Phobos object type")

    updateinertial = BoolProperty(
        name='robotupdate inertial',
        default=False,
        description='update inertials'
    )

    def execute(self, context):
        sourcelist = []
        targetlist = []
        processed = set()
        links = [obj.name for obj in bpy.context.selected_objects if obj.phobostype == 'link']
        t = dt.now()
        objdict = {obj.name: obj for obj in bpy.data.objects if obj.phobostype in ['visual', 'collision']
                   and obj.parent.name in links}
        # gather all name bases of objects for which both visual and collision are present
        for obj in objdict.keys():
            basename = obj.replace(objdict[obj].phobostype + '_', '')
            if 'visual_' + basename in objdict.keys() and 'collision_' + basename in objdict.keys():
                processed.add(basename)
        # fill source and target lists for syncing
        for basename in processed:
            if self.synctype == "vtc":
                sourcelist.append('visual_' + basename)
                targetlist.append('collision_' + basename)
            elif self.synctype == "ctv":
                targetlist.append('visual_' + basename)
                sourcelist.append('collision_' + basename)
            else:  # latest to oldest
                try:
                    tv = utility.datetimeFromIso(objdict['visual_' + basename]['masschanged'])
                    tc = utility.datetimeFromIso(objdict['collision_' + basename]['masschanged'])
                    if tc < tv:  #if collision information is older than visual information
                        sourcelist.append('visual_' + basename)
                        targetlist.append('collision_' + basename)
                    else:
                        targetlist.append('visual_' + basename)
                        sourcelist.append('collision_' + basename)
                except KeyError:
                    print(basename, "has insufficient data for time-based synchronisation of masses.")
        # sync the mass values
        for i in range(len(sourcelist)):
            try:
                objdict[targetlist[i]]['mass'] = objdict[sourcelist[i]]['mass']
            except KeyError:
                print("No mass information in object", targetlist[i])
            if self.synctype != "vtc" and self.synctype != "ctv":
                objdict[targetlist[i]]['masschanged'] = objdict[sourcelist[i]]['masschanged']

        for linkname in links:
            masssum = 0.0
            link = bpy.data.objects[linkname]
            viscols = inertia.getInertiaRelevantObjects(link)
            for obj in viscols:
                masssum += obj['mass']
            link['mass'] = masssum
            link['masschanged'] = t.isoformat()
            if self.updateinertial:
                inertia.createInertials(link)
        return {'FINISHED'}


class ShowDistanceOperator(Operator):
    """ShowDistanceOperator

    """
    bl_idname = "object.phobos_show_distance"
    bl_label = "Shows distance between two selected objects in world coordinates."
    bl_options = {'REGISTER', 'UNDO'}

    distance = FloatProperty(
        name="distance",
        default=0.0,
        subtype='DISTANCE',
        unit='LENGTH',
        precision=6,
        description="distance between objects")

    distVector = FloatVectorProperty(
        name="distanceVector",
        default=(0.0, 0.0, 0.0,),
        subtype='TRANSLATION',
        unit='LENGTH',
        size=3,
        precision=6,
        description="distance between objects")

    def execute(self, context):
        self.distance, self.distVector = utility.distance(bpy.context.selected_objects)
        return {'FINISHED'}


class SetXRayOperator(Operator):
    """SetXrayOperator

    """
    bl_idname = "object.phobos_set_xray"
    bl_label = "Shows the selected/chosen objects via X-Ray."
    bl_options = {'REGISTER', 'UNDO'}

    objects = EnumProperty(
        name="show objects:",
        default='selected',
        items=(('all',) * 3, ('selected',) * 3, ('by name',) * 3) + defs.phobostypes,
        description="show objects via x-ray")

    show = BoolProperty(
        name="show",
        default=True,
        description="set to")

    namepart = StringProperty(
        name="name contains",
        default="",
        description="part of a name for objects to be selected in 'by name' mode")

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' or context.mode == 'POSE'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select Items for X-Ray view")

        layout.prop(self, "objects")
        layout.prop(self, "show", text="x-ray enabled" if self.show else "x-ray disabled")
        if self.objects == 'by name':
            layout.prop(self, "namepart")

    def execute(self, context):
        if self.objects == 'all':
            objlist = bpy.data.objects
        elif self.objects == 'selected':
            objlist = bpy.context.selected_objects
        elif self.objects == 'by name':
            objlist = [obj for obj in bpy.data.objects if obj.name.find(self.namepart) >= 0]
        else:
            objlist = [obj for obj in bpy.data.objects if obj.phobostype == self.objects]
        for obj in objlist:
            obj.show_x_ray = self.show
        return {'FINISHED'}


class NameModelOperator(Operator):
    """NameModelOperator

    """
    bl_idname = "object.phobos_name_model"
    bl_label = "Name model by assigning 'modelname' property to root node "
    bl_options = {'REGISTER', 'UNDO'}

    modelname = StringProperty(
        name="modelname",
        default="",
        description="name of the robot model to be assigned")

    def execute(self, context):
        startLog(self)
        root = utility.getRoot(bpy.context.active_object)
        if root == None:
            log("Could not set modelname due to missing root link. No name was set.", "ERROR")
            return {'FINISHED'}
        root["modelname"] = self.modelname
        endLog()
        return {'FINISHED'}


class SelectObjectsByPhobosType(Operator):
    """SelectObjectsByPhobosType

    """
    bl_idname = "object.phobos_select_objects_by_phobostype"
    bl_label = "Select objects in the scene by phobostype"
    bl_options = {'REGISTER', 'UNDO'}

    seltype = EnumProperty(
        items=defs.phobostypes,
        name="phobostype",
        default="link",
        description="Phobos object type")

    def execute(self, context):
        objlist = []
        for obj in bpy.data.objects:
            if obj.phobostype == self.seltype:
                objlist.append(obj)
        utility.selectObjects(objlist, True)
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'


class SelectObjectsByName(Operator):
    """SelectObjectsByName

    """
    bl_idname = "object.phobos_select_objects_by_name"
    bl_label = "Select objects in the scene by their name"
    bl_options = {'REGISTER', 'UNDO'}

    namefragment = StringProperty (
            name = "name contains",
            default = '',
            description = "part of a Phobos object name")

    def execute(self, context):
        utility.selectByName(self.namefragment)
        return {'FINISHED'}


class SelectRootOperator(Operator):
    """SelectRootOperator

    """
    bl_idname = "object.phobos_select_root"
    bl_label = "Select root object(s) of currently selected object(s)"

    def execute(self, context):
        startLog(self)
        roots = set()
        for obj in bpy.context.selected_objects:
            roots.add(utility.getRoot(obj))
        if len(roots) > 0:
            utility.selectObjects(list(roots), True)
            bpy.context.scene.objects.active = list(roots)[0]
        else:
            # bpy.ops.error.message('INVOKE_DEFAULT', type="ERROR", message="Couldn't find any root object.")
            log("Couldn't find any root object.", "ERROR")
        endLog()
        return {'FINISHED'}


class SelectModelOperator(Operator):
    """SelectModelOperator

    """
    bl_idname = "object.phobos_select_model"
    bl_label = "Select all objects of model(s) containing the currently selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    modelname = StringProperty(
        name="modelname",
        default="",
        description="name of the model to be selected")

    def execute(self, context):
        selection = []
        if self.modelname:
            print("phobos: Selecting model", self.modelname)
            roots = utility.getRoots()
            for root in roots:
                if root["modelname"] == self.modelname:
                    selection = utility.getChildren(root)
        else:
            print("phobos: No model name provided, deriving from selection...")
            roots = set()
            for obj in bpy.context.selected_objects:
                print("Selecting", utility.getRoot(obj).name)
                roots.add(utility.getRoot(obj))
            for root in list(roots):
                selection.extend(utility.getChildren(root))
        utility.selectObjects(list(selection), True)
        return {'FINISHED'}


class UpdatePhobosModelsOperator(Operator):
    """UpdatePhobosModelsOperator

    """
    bl_idname = "object.phobos_update_models"
    bl_label = "Update Phobos properties for all objects"
    bl_options = {'REGISTER', 'UNDO'}

    property_fix = BoolProperty(
        name = 'fix',
        default = False,
        description = "try to fix detected errors?")

    print("phobos: Updating Phobos properties for selected objects...")

    def execute(self, context):
        materials.createPhobosMaterials()  # TODO: this should move to initialization
        robotupdate.updateModels(utility.getRoots(), self.property_fix)
        return {'FINISHED'}


class SetPhobosType(Operator):
    """Set phobostype Operator

    """
    bl_idname = "object.phobos_set_phobostype"
    bl_label = "Edit phobostype of selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    phobostype = EnumProperty (
            items = defs.phobostypes,
            name = "phobostype",
            default = "undefined",
            description = "phobostype")

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            obj.phobostype = self.phobostype
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT'


class BatchEditPropertyOperator(Operator):
    """Batch-Edit Property Operator

    """
    bl_idname = "object.phobos_batch_property"
    bl_label = "Edit custom property of selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    property_name = StringProperty(
        name="property_name",
        default="",
        description="custom property name")

    property_value = StringProperty(
        name="property_value",
        default="",
        description="custom property value")

    def execute(self, context):
        value = utility.parse_number(self.property_value)
        if value == '':
            for obj in bpy.context.selected_objects:
                if self.property_name in obj:
                    del(obj[self.property_name])
        else:
            for obj in bpy.context.selected_objects:
                obj[self.property_name] = value
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT'


class CopyCustomProperties(Operator):
    """Copy Custom Properties Operator

    """
    bl_idname = "object.phobos_copy_props"
    bl_label = "Edit custom property of selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    empty_properties = BoolProperty(
        name='empty',
        default=False,
        description="empty properties?")

    def execute(self, context):
        slaves = context.selected_objects
        master = context.active_object
        slaves.remove(master)
        props = robotdictionary.cleanObjectProperties(dict(master.items()))
        for obj in slaves:
            if self.empty_properties:
                for key in obj.keys():
                    del(obj[key])
            for key in props.keys():
                obj[key] = props[key]
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        obs = context.selected_objects
        ob = context.active_object
        return len(obs) > 0 and ob is not None and ob.mode == 'OBJECT'


class RenameCustomProperty(Operator):
    """Rename Custom Properties Operator

    """
    bl_idname = "object.phobos_rename_custom_property"
    bl_label = "Edit custom property of selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    find = StringProperty(
        name="find property name:",
        default='',
        description="name to be searched for")

    replace = StringProperty(
        name="replacement name:",
        default='',
        description="new name to be replaced with")

    overwrite = BoolProperty(
        name='overwrite existing properties',
        default=False,
        description="If a property of the specified replacement name exists, overwrite it?"
    )

    def execute(self, context):
        startLog(self)
        for obj in context.selected_objects:
            if self.find in obj and self.replace != '':
                if self.replace in obj:
                    # print("### Error: property", self.replace, "already present in object", obj.name)
                    log("Property '" + self.replace + "' already present in object '" + obj.name + "'", "ERROR")
                    if self.overwrite:
                        log("Replace property, because overwrite option was set")
                        obj[self.replace] = obj[self.find]
                        del obj[self.find]
                else:
                    obj[self.replace] = obj[self.find]
                    del obj[self.find]
        endLog()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT' and len(context.selected_objects) > 0


class SetGeometryType(Operator):
    """Set Geometry Type Operator

    """
    bl_idname = "object.phobos_set_geometry_type"
    bl_label = "Edit geometry type of selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    geomType = EnumProperty (
            items=defs.geometrytypes,
            name="type",
            default="box",
            description="Phobos geometry type")

    def execute(self, context):
        startLog(self)
        for obj in bpy.context.selected_objects:
            if obj.phobostype == 'collision' or obj.phobostype == 'visual':
                obj['geometry/type'] = self.geomType
            else:
                log("The object '" + obj.name + "' is no collision or visual")
        endLog()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT' and len(context.selected_objects) > 0


class EditInertia(Operator):
    """Edit Inertia Operator

    """
    bl_idname = "object.phobos_edit_inertia"
    bl_label = "Edit inertia of selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    # inertiamatrix = FloatVectorProperty (
    #        name = "inertia",
    #        default = [0, 0, 0, 0, 0, 0, 0, 0, 0],
    #        subtype = 'MATRIX',
    #        size = 9,
    #        description = "set inertia for a link")

    inertiavector = FloatVectorProperty(
        name="inertiavec",
        default=[0, 0, 0, 0, 0, 0],
        subtype='NONE',
        size=6,
        description="set inertia for a link"
    )

    def invoke(self, context, event):
        if 'inertia' in context.active_object:
            self.inertiavector = mathutils.Vector(context.active_object['inertia'])
        return self.execute(context)

    def execute(self, context):
        #m = self.inertiamatrix
        #inertialist = []#[m[0], m[1], m[2], m[4], m[5], m[8]]
        #obj['inertia'] = ' '.join(inertialist)
        for obj in context.selected_objects:
            if obj.phobostype == 'inertial':
                obj['inertia'] = self.inertiavector  #' '.join([str(i) for i in self.inertiavector])
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT' and ob.phobostype == 'inertial' and len(
            context.selected_objects) > 0


class PartialRename(Operator):
    """Partial Rename Operator

    """
    bl_idname = "object.phobos_partial_rename"
    bl_label = "Replace part of the name of selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    find = StringProperty(
        name="find",
        default="",
        description="find string")

    replace = StringProperty(
        name="replace",
        default="",
        description="replace with")

    def execute(self, context):
        types = defs.subtypes
        for obj in bpy.context.selected_objects:
            obj.name = obj.name.replace(self.find, self.replace)
            for type in types:
                nametag = type+"/name"
                if nametag in obj:
                    obj[nametag] = obj[nametag].replace(self.find, self.replace)
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT' and len(context.selected_objects) > 0


class SmoothenSurfaceOperator(Operator):
    """SmoothenSurfaceOperator

    """
    bl_idname = "object.phobos_smoothen_surface"
    bl_label = "Smoothen Selected Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        show_progress = bpy.app.version[0] * 100 + bpy.app.version[1] >= 269;
        if show_progress:
            wm = bpy.context.window_manager
            total = float(len(bpy.context.selected_objects))
            wm.progress_begin(0, total)
            i = 1
        for obj in bpy.context.selected_objects:
            if obj.type != 'MESH':
                continue
            bpy.context.scene.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all()
            bpy.ops.mesh.normals_make_consistent()
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.shade_smooth()
            bpy.ops.object.modifier_add(type='EDGE_SPLIT')
            if show_progress:
                wm.progress_update(i)
                i += 1
        if show_progress:
            wm.progress_end()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT' and len(context.selected_objects) > 0


class SetOriginToCOMOperator(Operator):
    """SetOriginToCOMOperator

    """
    bl_idname = "object.phobos_set_origin_to_com"
    bl_label = "Set Origin to COM"
    bl_options = {'REGISTER', 'UNDO'}

    com_shift = FloatVectorProperty(
        name="CAD origin shift",
        default=(0.0, 0.0, 0.0,),
        subtype='TRANSLATION',
        unit='LENGTH',
        size=3,
        precision=6,
        description="distance between objects")

    cursor_location = FloatVectorProperty(
        name="CAD origin",
        default=(0.0, 0.0, 0.0,),
        subtype='TRANSLATION',
        unit='LENGTH',
        size=3,
        precision=6,
        description="distance between objects")

    def execute(self, context):
        master = context.active_object
        slaves = context.selected_objects
        to_cadorigin = self.cursor_location - master.matrix_world.to_translation()
        com_shift_world = to_cadorigin + self.com_shift
        for s in slaves:
            utility.selectObjects([s], True, 0)
            context.scene.cursor_location = s.matrix_world.to_translation() + com_shift_world
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        utility.selectObjects(slaves, True, slaves.index(master))
        context.scene.cursor_location = self.cursor_location.copy()
        return {'FINISHED'}

    def invoke(self, context, event):
        self.cursor_location = context.scene.cursor_location.copy()
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT' and len(context.selected_objects) > 0


class CreateInertialOperator(Operator):
    """CreateInertialOperator

    """
    bl_idname = "object.create_inertial_objects"
    bl_label = "Creates inertial objects based on existing objects"
    bl_options = {'REGISTER', 'UNDO'}

    auto_compute = BoolProperty(
        name='calculate automatically',
        default=True,
        description='calculate inertia automatically'
    )

    preserve_children = BoolProperty(
        name='preserve child inertials',
        default=False,
        description='preserve child inertials'
    )

    def execute(self, context):
        links = [obj for obj in bpy.context.selected_objects if obj.phobostype == 'link']
        show_progress = bpy.app.version[0] * 100 + bpy.app.version[1] >= 269
        if show_progress:
            wm = bpy.context.window_manager
            total = float(len(links))
            wm.progress_begin(0, total)
            i = 1
        for link in links:
            inertia.createInertials(link, not self.auto_compute, self.preserve_children)
            if show_progress:
                wm.progress_update(i)
                i += 1
        if show_progress:
            wm.progress_end()
        return {'FINISHED'}


class AddGravityVector(Operator):
    """Add Gravity Operator

    """
    bl_idname = "object.phobos_add_gravity"
    bl_label = "Add a vector representing gravity in the scene"
    bl_options = {'REGISTER', 'UNDO'}

    property_name = FloatVectorProperty(
        name="gravity_vector",
        default=(0, 0, -9.81),
        description="gravity vector")

    def execute(self, context):
        bpy.ops.object.empty_add(type='SINGLE_ARROW')
        bpy.context.active_object.name = "gravity"
        bpy.ops.transform.rotate(value=(math.pi), axis=(1.0, 0.0, 0.0))
        return {'FINISHED'}


class SetLogSettings(Operator):
    """Adjust Logging Settings for phobos

    """
    bl_idname = 'object.phobos_adjust_logger'
    bl_label = "Change the detail of the phobos logger"
    bl_options = {'REGISTER', 'UNDO'}

    isEnabled = BoolProperty(
        name="Enable logging",
        default=True,
        description="Enable log messages (INFOS will still appear)"
    )

    errors = BoolProperty(
        name="Show Errors",
        default=True,
        description="Show errors in log"
    )

    warnings = BoolProperty(
        name="Show Warnings",
        default=True,
        description="Show warnings in log"
    )

    def execute(self, context):
        adjustLevel("ALL", self.isEnabled)
        adjustLevel("ERROR", self.errors)
        adjustLevel("WARNING", self.warnings)
        return {'FINISHED'}


class EditYAMLDictionary(Operator):
    """Edit a dictionary as YAML in text file."""
    bl_idname = 'object.phobos_edityamldictionary'
    bl_label = "Edit object dictionary as YAML"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        startLog(self)
        ob = context.active_object
        textfilename = ob.name + dt.now().strftime("%Y%m%d_%H:%M")
        variablename = ob.name.translate({ord(c): "_" for c in "!@#$%^&*()[]{};:,./<>?\|`~-=+"})\
                       + "_data"
        tmpdict = dict(ob.items())
        for key in tmpdict:
            if hasattr(tmpdict[key], 'to_list'):  # transform Blender id_arrays into lists
                tmpdict[key] = list(tmpdict[key])
        contents = [variablename + ' = """',
                    yaml.dump(utility.cleanObjectProperties(tmpdict),
                              default_flow_style=False) + '"""\n',
                    "# ------- Hit 'Run Script' to save your changes --------",
                    "import yaml", "import bpy",
                    "tmpdata = yaml.load(" + variablename + ")",
                    "for key, value in tmpdata.items():",
                    "    bpy.context.active_object[key] = value",
                    "bpy.ops.text.unlink()"
                    ]
        utility.createNewTextfile(textfilename, '\n'.join(contents))
        utility.openScriptInEditor(textfilename)
        endLog()
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.mode == 'OBJECT' and len(context.selected_objects) > 0


class WarningDialogOperator(Operator):
    """
    Display a warning inside a dialog.
    """
    bl_idname = "tools.phobos_warning_dialog"
    bl_label = "Warning."

    message = bpy.props.StringProperty(name="Message")

    def invoke(self, context, event):
        # to check whether this is being called:
        #self.report({'WARNING'}, "CALLED")
        return context.window_manager.invoke_props_dialog(self, width=len(self.message)*15)

    def execute(self, context):
        #print(self.message)
        return {'FINISHED'}

# the following code is used to directly add buttons to current operator menu
# - we don't need that if we create a custom toolbar with pre-defined buttons
# def add_object_button(self, context):
#     self.layout.operator(
#         BatchEditPropertyOperator.bl_idname,
#         text=BatchEditPropertyOperator.__doc__,
#         icon='PLUGIN')
