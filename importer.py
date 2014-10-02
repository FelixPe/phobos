#!/usr/bin/python

"""
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

File importer.py

Created on 28 Feb 2014

@author: Kai von Szadkowski
"""

import bpy
import mathutils
import os
import yaml
from collections import namedtuple
import xml.etree.ElementTree as ET
from phobos.utility import *
from . import defs
from . import materials

#This is a really nice pythonic approach to creating a list of constants
Defaults = namedtuple('Defaults', ['mass', 'idtransform'])
defaults = Defaults(0.001, #mass
                    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] #idtransform
                    )

def register():
    print("Registering importer...")

def unregister():
    print("Unregistering importer...")

def cleanUpScene():
    # select all objects
    bpy.ops.object.select_all(action="SELECT")

    # and delete them
    bpy.ops.object.delete()

    # after that we have to clean up all loaded meshes (unfortunately
    # this is not done automatically)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)

    # and all materials
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)

    # and all lights (aka lamps)
    for lamp in bpy.data.lamps:
        bpy.data.lamps.remove(lamp)


class RobotModelParser():
    """Base class for a robot model file parser of a specific type"""

    def __init__(self, filepath):
        self.filepath = filepath
        self.path, self.filename = os.path.split(self.filepath)
        self.robot = {}

    def placeChildLinks(self, parent):
        print(parent['name']+ ', ', end='')
        children = []
        for l in self.robot['links']:
            if 'parent' in self.robot['links'][l] and self.robot['links'][l]['parent'] == parent['name']:
                children.append(self.robot['links'][l])
        for child in children:
            # 1: set parent relationship (this makes the parent inverse the inverse of the parents world transform)
            parentLink = bpy.data.objects[parent['name']]
            childLink = bpy.data.objects[child['name']]
            bpy.ops.object.select_all(action="DESELECT") #bpy.context.selected_objects = []
            childLink.select = True
            parentLink.select = True
            bpy.context.scene.objects.active = parentLink
            bpy.ops.object.parent_set(type='BONE_RELATIVE')
            # 2: move to parents origin by setting the world matrix to the parents world matrix
            childLink.matrix_world = parentLink.matrix_world
            # 3: apply local transform as saved in urdf (change matrix_local from identity to urdf)
            urdf_loc = mathutils.Matrix.Translation(child['pose'][0:3])
            urdf_rot = mathutils.Euler(tuple(child['pose'][3:]), 'XYZ').to_matrix().to_4x4()
            urdfmatrix = urdf_loc * urdf_rot
            childLink.matrix_local = urdfmatrix
            # 4: be happy, as world and basis are now the same and local is the transform to be exported to urdf
            # 5: take care of the rest of the tree
            self.placeChildLinks(child)

    def placeLinkSubelements(self, link):
        #urdf_sca = #TODO: solve problem with scale
        # 3.2: make sure to take into account visual information #TODO: also take into account inertial and joint axis (for joint sphere) and collision (bounding box)
        #* urdf_visual_loc * urdf_visual_rot #*urdf_sca
        parentLink = bpy.data.objects[link['name']]
        if 'inertial' in link:
            if 'pose' in link['inertial']:
                urdf_geom_loc = mathutils.Matrix.Translation(link['inertial']['pose'][0:3])
                urdf_geom_rot = mathutils.Euler(tuple(link['inertial']['pose'][3:]), 'XYZ').to_matrix().to_4x4()
            else:
                urdf_geom_loc = mathutils.Matrix.Identity(4)
                urdf_geom_rot = mathutils.Matrix.Identity(4)
            inertialname = link['inertial']['name']
            inertialobj = bpy.data.objects[inertialname]
            bpy.ops.object.select_all(action="DESELECT")
            inertialobj.select = True
            parentLink.select = True
            bpy.context.scene.objects.active = parentLink
            bpy.ops.object.parent_set(type='BONE_RELATIVE')
            inertialobj.matrix_local = urdf_geom_loc * urdf_geom_rot
        for geomsrc in ['visual', 'collision']:
            if geomsrc in link:
                for g in link[geomsrc]:
                    geomelement = link[geomsrc][g]
                    if 'pose' in geomelement:
                        urdf_geom_loc = mathutils.Matrix.Translation(geomelement['pose'][0:3])
                        urdf_geom_rot = mathutils.Euler(tuple(geomelement['pose'][3:]), 'XYZ').to_matrix().to_4x4()
                    else:
                        urdf_geom_loc = mathutils.Matrix.Identity(4)
                        urdf_geom_rot = mathutils.Matrix.Identity(4)
                    geoname = geomelement['name']
                    geom = bpy.data.objects[geoname]
                    # FIXME: this does not do anything - how to set basis matrix to local?
                    #geom.matrix_world = parentLink.matrix_world
                    bpy.ops.object.select_all(action="DESELECT")
                    geom.select = True
                    parentLink.select = True
                    bpy.context.scene.objects.active = parentLink
                    bpy.ops.object.parent_set(type='BONE_RELATIVE')
                    geom.matrix_local = urdf_geom_loc * urdf_geom_rot

    def createGeometry(self, viscol, geomsrc):
        newgeom = None
        if viscol['geometry'] is not {}:
            dimensions = None
            bpy.ops.object.select_all(action='DESELECT')
            geom = viscol['geometry']
            geomtype = geom['type']
            # create the Blender object
            # tag all objects
            for obj in bpy.data.objects:
                obj.tag = True
            if geomtype == 'mesh':
                filetype = geom['filename'].split('.')[-1]
                if filetype == 'obj' or filetype == 'OBJ':
                    bpy.ops.import_scene.obj(filepath=os.path.join(self.path, geom['filename']))
                elif filetype == 'stl' or filetype == 'STL':
                    bpy.ops.import_mesh.stl(filepath=os.path.join(self.path, geom['filename']))
                # find the newly imported obj
                for obj in bpy.data.objects:
                    if not obj.tag:
                        newgeom = obj
                        #with obj file import, blender only turns the object, not the vertices,
                        #leaving a rotation in the matrix_basis, which we here get rid of
                        if filetype == 'obj':
                            bpy.ops.object.select_all(action='DESELECT')
                            newgeom.select = True
                            bpy.ops.object.transform_apply(rotation=True)
                newgeom.name = viscol['name']
                newgeom['filename'] = geom['filename']
                #newgeom.select = True
                #if 'scale' in geom:
                #    newgeom.scale = geom['scale']
                #bpy.ops.object.transform_apply(scale=True)
            elif geomtype == 'box':
                dimensions = geom['size']
            elif geomtype == 'cylinder':
                dimensions = (geom['radius'], geom['length'])
            elif geomtype == 'sphere':
                dimensions = geom['radius']
            else:
                print("### ERROR: Could not determine geometry type of " + geomsrc + viscol['name'] + '. Placing empty coordinate system.')
            if dimensions:  # if a standard primitive type is found, create the object
                newgeom = createPrimitive(viscol['name'], geomtype, dimensions, defs.layerTypes[geomsrc])
                newgeom.select = True
                bpy.ops.object.transform_apply(scale=True)
            if newgeom is not None:
                newgeom.MARStype = geomsrc
                newgeom['geometry/type'] = geomtype
            #FIXME: place empty coordinate system and return...what? Error handling of file import!
        return newgeom

    def createInertial(self, name, inertial):
        bpy.ops.object.select_all(action='DESELECT')
        inert = createPrimitive('inertial_'+name, 'box', [0.01, 0.01, 0.01], 0, 'None', (0, 0, 0))
        inert.select = True
        bpy.ops.object.transform_apply(scale=True)
        for prop in inertial:
            if prop not in ['pose'] and inertial[prop] is not None:
                inert[prop] = inertial[prop]
        inert.MARStype = 'inertial'
        return inert

    def createLink(self, link):
        #create base object ( =armature)
        bpy.ops.object.select_all(action='DESELECT')
        #bpy.ops.view3d.snap_cursor_to_center()
        bpy.ops.object.armature_add(layers=defLayers([0]))
        newlink = bpy.context.active_object #print(bpy.context.object) #print(bpy.context.scene.objects.active) #bpy.context.selected_objects[0]
        newlink.name = link['name']
        newlink.location = (0.0, 0.0, 0.0)
        newlink.scale = (0.3, 0.3, 0.3) #TODO: make this depend on the largest visual or collision object
        bpy.ops.object.transform_apply(scale=True)
        newlink.MARStype = 'link'
        if newlink.name != link['name']:
            print("Warning, name conflict!")
        # place inertial
        if 'inertial' in link:
            self.createInertial(link['name'], link['inertial'])
        # place visual
        if 'visual' in link:
            for v in link['visual']:
                visual = link['visual'][v]
                if 'geometry' in visual:
                    self.createGeometry(visual, 'visual')
        # place collision
        if 'collision' in link:
            for c in link['collision']:
                collision = link['collision'][c]
                if 'geometry' in collision:
                    self.createGeometry(collision, 'collision')
        return newlink

    def createBlenderModel(self): #TODO: solve problem with duplicated links (linklist...namespaced via robotname?)
        """Creates the blender object representation of the imported model."""
        print("\n\nCreating Blender model...")
        print("Creating links...")
        for l in self.robot['links']:
            print(l + ', ', end='')
            link = self.robot['links'][l]
            self.createLink(link)

        #build tree recursively and correct translation & rotation on the fly
        for l in self.robot['links']:
            if not 'parent' in self.robot['links'][l]:
                root = self.robot['links'][l]
        print("\n\nPlacing links...")
        self.placeChildLinks(root)
        print("\n\nAssigning model name...")
        try:
            rootlink = getRoot(bpy.data.objects[root['name']])
            rootlink['modelname'] = self.robot['name']
        except KeyError:
            print("### Error: Could not assign model name to root link.")
        for link in self.robot['links']:
            self.placeLinkSubelements(self.robot['links'][link])




class MARSModelParser(RobotModelParser):
    """Class derived from RobotModelParser which parses a MARS scene"""

    def __init__(self, filepath):
        RobotModelParser.__init__(filepath)

    def parseModel(self):
        print("Parsing MARS scene...")


class URDFModelParser(RobotModelParser):
    """Class derived from RobotModelParser which parses a URDF model"""

    def __init__(self, filepath):
        RobotModelParser.__init__(self, filepath)

    def parseModel(self):
        print("\nParsing URDF model from", self.filepath)
        self.tree = ET.parse(self.filepath)
        self.root = self.tree.getroot()#[0]
        self.robot["name"] = self.root.attrib["name"]
        if 'version' in self.root.attrib:
            self.robot["version"] = self.root.attrib['version'] #TODO: implement version functionality (time code)

        #write links to dictionary
        links = {}
        print("\n\nParsing links..")
        for link in self.root.iter('link'):
            newlink = self.parseLink(link)
            #write link to list
            links[newlink['name']] = newlink
        self.robot['links'] = links

        #write joints to dictionary
        joints = {}
        print("\n\nParsing joints..")
        for joint in self.root.iter('joint'):
            if joint.find('parent') is not None: #this is needed as there are "joint" tags e.g. in transmission
                newjoint, pose = self.parseJoint(joint)
                self.robot['links'][newjoint['child']]['pose'] = pose
                joints[newjoint['name']] = newjoint
        self.robot['joints'] = joints

        #find any links that still have no pose (most likely because they had no parent)
        for link in links:
            if not 'pose' in links[link]:
                links[link]['pose'] = defaults.idtransform

        #write parent-child information to nodes
        print("\n\nWriting parent-child information to nodes..")
        for j in self.robot['joints']:
            joint = self.robot['joints'][j]
            self.robot['links'][joint['child']]['parent'] = joint['parent']
            print(joint['parent'] + ', ', end='')

        #now some debug output
        with open(self.filepath+'_debug.yml', 'w') as outputfile:
            outputfile.write(yaml.dump(self.robot))#, default_flow_style=False)) #last parameter prevents inline formatting for lists and dictionaries

        materiallist = [] #TODO: build dictionary entry for materials
        print("\n\nParsing materials..")
        for material in self.root.iter('material'):
            newmaterial = {a: material.attrib[a] for a in material.attrib}
            color = material.find('color')
            if color is not None:
                print(material.attrib['name'] + ', ', end='')
                newmaterial['color'] = parse_text(color.attrib['rgba'])
                materiallist.append(newmaterial)
        for m in materiallist:
            materials.makeMaterial(m['name'], tuple(m['color'][0:3]), (1, 1, 1), m['color'][-1]) #TODO: handle duplicate names? urdf_robotname_xxx?

    def parseLink(self, link):
        print(link.attrib['name'] + ', ', end='')
        newlink = {a: link.attrib[a] for a in link.attrib}

        #parse 'inertial'
        inertial = link.find('inertial')
        if inertial is not None: # 'if Element' yields none if the Element contains no children, thus this notation
            newlink['inertial'] = {}
            origin = inertial.find('origin')
            if origin is not None:
                newlink['inertial']['pose'] = [float(num) for num in (origin.attrib['xyz'].split() + origin.attrib['rpy'].split())]
            else:
                newlink['inertial']['pose'] = defaults.idtransform
            mass = inertial.find('mass')
            if mass is not None:
                newlink['inertial']['mass'] = float(mass.attrib['value'])
            inertia = inertial.find('inertia')
            if inertia is not None:
                values = []
                newlink['inertial']['inertia'] = values.append(inertia.attrib[a] for a in inertia.attrib)
            newlink['inertial']['name'] = 'inertial_' + newlink['name']

        #parse visual and collision objects
        for type in ['visual', 'collision']:
            newlink[type] = {}
            i=0
            for xmlelement in link.iter(type):
                try:
                    elementname = xmlelement.attrib['name']
                except KeyError:
                    elementname = type + '_' + str(i) + '_' + newlink['name']
                    i += 1
                newlink[type][elementname] = {a: xmlelement.attrib[a] for a in xmlelement.attrib}
                dictelement = newlink[type][elementname]
                dictelement['name'] = elementname
                origin = xmlelement.find('origin')
                if origin is not None:
                    dictelement['pose'] = [float(num) for num in (origin.attrib['xyz'].split() + origin.attrib['rpy'].split())]
                else:
                    dictelement['pose'] = defaults.idtransform
                geometry = xmlelement.find('geometry')
                if geometry is not None:
                    dictelement['geometry'] = {a: parse_text(geometry[0].attrib[a]) for a in geometry[0].attrib}
                    dictelement['geometry']['type'] = geometry[0].tag
                    novisual = False
                    if geometry[0].tag == 'mesh':
                        dictelement['geometry']['filename'] = geometry[0].attrib['filename']
                        try:
                            dictelement['geometry']['scale'] = parse_text(geometry[0].attrib['scale'])
                        except KeyError:
                            dictelement['geometry']['scale'] = [1.0, 1.0, 1.0]
                material = xmlelement.find('material')
                if material is not None:
                    dictelement['material'] = {'name': material.attrib['name']}
                    color = material.find('color')
                    if color is not None:
                        dictelement['material']['color'] = parse_text(color.attrib['rgba'])
        return newlink

    def parseJoint(self, joint):
        print(joint.attrib['name']+', ', end='')
        newjoint = {a: joint.attrib[a] for a in joint.attrib}
        try:
            origin = joint.find('origin')
            origindict = {'xyz': origin.attrib['xyz'].split(), 'rpy': origin.attrib['rpy'].split()}
        except AttributeError:
            origindict = {'xyz': [0, 0, 0], 'rpy': [0, 0, 0]}
        newjoint['parent'] = joint.find('parent').attrib['link']
        newjoint['child'] = joint.find('child').attrib['link']
        pose = [float(num) for num in (origindict['xyz'] + origindict['rpy'])]
        #axis
        #calibration
        #dynamics
        #limit
        #mimic
        #safety_controller
        return newjoint, pose

class SMURFModelParser(RobotModelParser):
    """Class derived from RobotModelParser which parses a SMURF model"""

    def __init__(self, filepath):
        RobotModelParser.__init__(filepath)

    def parseModel(self):
        print("Parsing SMURF model...")


class RobotModelImporter(bpy.types.Operator):
    """Importer for MARS-compatible model or scene files"""
    bl_idname = "obj.import_robot_model"
    bl_label = "Import robot model file from various formats"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'FILE'

    # creating property for storing the path to the .scn file
    filepath = bpy.props.StringProperty(subtype="FILE_PATH")

    # set a filter to only consider .scn files (only used internally)
    #filter_glob = bpy.props.StringProperty(default="*.*",options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context is not None

    def execute(self, context):
        # get the chosen file path
        #directory, filename = os.path.split(self.filepath)
        modeltype = self.filepath.split('.')[-1]

        if modeltype == 'scene':
            importer = MARSModelParser(self.filepath)
        elif modeltype == 'urdf':
            importer = URDFModelParser(self.filepath)
        elif modeltype == 'smurf' or modeltype == 'yml' or modeltype == 'yaml':
            importer = SMURFModelParser(self.filepath)
        else:
            print("Unknown model format, aborting import...")

        importer.parseModel()
        importer.createBlenderModel()

        return {'FINISHED'}

    def invoke(self, context, event):
        # create the open file dialog
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

# Register and add to the file selector
bpy.utils.register_class(RobotModelImporter)


def main():
    # call the newly registered operator
    cleanUpScene()
    bpy.ops.import_robot_model('INVOKE_DEFAULT')

if __name__ == '__main__':
    main()
