# -*- coding: utf-8 -*-
"""
Created on Wed Mar  6 13:38:47 2019

@author: AsteriskAmpersand
Modified for Blender 4.4 compatibility
"""
#from .dbg import dbg_init
#dbg_init()

content=bytes("","UTF-8")
bl_info = {
    "name": "Easier MHW Mod3 Import_Export",
    "category": "Import-Export",
    "author": "AsteriskAmpersand (Code) & CrazyT (Structure) & 诸葛不太亮(Modify) & Assistant (4.4 Update)",
    "location": "File > Import-Export",
    "version": (2,1,0),
    "blender": (4, 4, 0),
    "description": "Import and Export Mod3 files for Monster Hunter World - Updated for Blender 4.4"
}
 
import bpy

from .operators.mod3import import ImportMOD3
from .operators.mod3export import ExportMOD3
from .operators.mod3import import menu_func_import
from .operators.mod3export import menu_func_export

classes = (
    ImportMOD3,
    ExportMOD3,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()