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

File __init__.py

Created on 6 Jan 2014

@author: Kai von Szadkowski, Ole Schwiegert
"""


bl_info = {
    "name": "Phobos",
    "description": "A set of tools to enable editing of MARS robot models in Blender.",
    "author": "Kai von Szadkowski, Malte Langosz, Stefan Rahms, Ole Schwiegert",
    "version": (0, 3),
    "blender": (2, 69, 0),
    "location": "Phobos adds a number of custom tool panels.",
    "warning": "",
    "wiki_url": "",
    "category": "Development"
    }

import sys
import os.path
yamlconfpath=sys.path[0]+"/phobos/yamlpath.conf"
if (os.path.isfile(yamlconfpath)):
    f = open(yamlconfpath)
    path = f.read()
    f.close()
    if (path == "v" or path == "i"):
        print("There is no YAML installation for python 3.4 or greater on this computer")
    else:
        print("Importing yaml module")
        sys.path.insert(0, path)
        import yaml
else:
    print("Could not find yamlpath.conf")
    print("Using distributed package instead!")
    sys.path.insert(0, sys.path[0]+"/phobos")
    import yaml
    print("Importing yaml module")

if "bpy" in locals():
    import imp
    imp.reload(robotupdate)
    imp.reload(robotdictionary)
    imp.reload(controllers)
    imp.reload(exporter)
    imp.reload(importer)
    imp.reload(phobosgui)
    imp.reload(joints)
    imp.reload(links)
    imp.reload(misctools)
    imp.reload(sensors)
    imp.reload(utility)
    imp.reload(collision)
    imp.reload(inertia)
    imp.reload(marssceneexport)
    print("Reloading Phobos.")
else:
    from . import robotupdate, links, marssceneexport, robotdictionary, controllers, exporter, importer, joints, misctools, sensors, utility, collision, inertia, phobosgui
    print("Importing Phobos modules.")

import bpy


def register():
    links.register()
    controllers.register()
    exporter.register()
    phobosgui.register()
    importer.register()
    joints.register()
    misctools.register()
    sensors.register()
    utility.register()
    collision.register()
    inertia.register()
    bpy.utils.register_module(__name__)

def unregister():
    links.unregister()
    controllers.unregister()
    exporter.unregister()
    phobosgui.unregister()
    importer.unregister()
    joints.unregister()
    misctools.unregister()
    sensors.unregister()
    utility.unregister()
    collision.unregister()
    inertia.register()
    bpy.utils.unregister_module(__name__)

#if __name__ == "__main__":
#    register()
