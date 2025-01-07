# -*- coding: utf-8 -*-
"""
Created on Wed Mar  6 14:09:29 2019

@author: AsteriskAmpersand
"""
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

from ..mod3 import Mod3ImporterLayer as Mod3IL
from ..blender import BlenderMod3Importer as Api
from ..blender import BlenderSupressor
from ..common import FileLike as FL


class Context():
    def __init__(self, path, meshes, armature):
        self.path = path
        self.meshes = meshes
        self.armature = armature
        self.setDefaults = False

class ImportMOD3(Operator, ImportHelper):
    bl_idname = "custom_import.import_mhw_mod3"
    bl_label = "Load MHW MOD3 file (.mod3)"
    bl_options = {'REGISTER', 'PRESET', 'UNDO'}
 
    # ImportHelper mixin class uses this
    filename_ext = ".mod3"
    filter_glob: StringProperty(default="*.mod3", options={'HIDDEN'}, maxlen=255)

    clear_scene: BoolProperty(
        name = "Clear scene before import.",
        description = "Clears all contents before importing",
        default = False,
        options={'HIDDEN'})
    maximize_clipping: BoolProperty(
        name = "Maximizes clipping distance.",
        description = "Maximizes clipping distance to be able to see all of the model at once.",
        default = False,
        options={'HIDDEN'})
    high_lod: BoolProperty(
        name = "Only import high LOD parts.",
        description = "Skip meshparts with low level of detail.",
        default = True)
    import_header: BoolProperty(
        name = "Import File Header.",
        description = "Imports file headers as scene properties.",
        default = True)
    independent_skeleton: BoolProperty(
        name = "Preserve Mesh-Skeleton Independence",
        description = "Avoids applying modifiers to mesh that force-link it to the skeleton.",
        default = True)
    import_meshparts: BoolProperty(
        name = "Import Meshparts.",
        description = "Imports mesh parts as meshes.",
        default = True)
    import_unknown_mesh_props: BoolProperty(
        name = "Import Unknown Mesh Properties.",
        description = "Imports the Unknown section of the mesh collection as scene property.",
        default = True)
    import_textures: BoolProperty(
        name = "Import Textures.",
        description = "Imports texture as specified by mrl3.",
        default = False,
        options={'HIDDEN'})
    texture_path: StringProperty(
        name = "Texture Source",
        description = "Root directory for the MRL3 (Native PC if importing from a chunk).",
        default = "")
    import_skeleton: EnumProperty(
        name = "Import Skeleton.",
        description = "Imports the skeleton as an armature.",
        items = [("None","Don't Import","Does not import the skeleton.",0),
                  
                  ("Armature","Animation Armature","Import the skeleton as a blender armature",1),
                  ],
        default = "Armature") 
    weight_format: EnumProperty(
        name = "Weight Format",
        description = "Preserves capcom scheme of having repeated weights and negative weights by having multiple weight groups for each bone.",
        items = [("Group","Standard","Weights under the same bone are grouped",0),
                  ("Split","Split Weight Notation","Mirrors the Mod3 separation of the same weight",1),
                  ("Slash","Split-Slash Notation","As split weight but also conserves weight order",2),
                  ],
        default = "Group")
    override_defaults: BoolProperty(
        name = "Override Default Mesh Properties.",
        description = "Overrides program defaults with default properties from the first mesh in the file.",
        default = False)

    def execute(self,context):
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        bpy.ops.object.select_all(action='DESELECT')
        Mod3File = FL.FileLike(open(self.properties.filepath,'rb').read())
        BApi = Api.BlenderImporterAPI()
        options = self.parseOptions()
        #print(options["Split Weights"])
        blenderContext = Context(self.properties.filepath,None,None)
        with BlenderSupressor.SupressBlenderOps():
            Mod3IL.Mod3ToModel(Mod3File, BApi, options).execute(blenderContext)   
   
        Armature_Name = bpy.context.active_object.data.name
        obj = bpy.context.active_object.data.bones 

        name_func = [["",""]]*len(obj)

        for i in range(len(obj)):
            if "boneFunction" not in obj[i].keys():
                name_func[i] = [obj[i].name, "255"]
            else:
                #name_func[i] = [obj[i].name,str(obj[i]["boneFunction"])]
                name_func[i] = [obj[i].name,"%03d"%obj[i]["boneFunction"]]
        #print(name_func)

        for i in range(len(obj)):
            name_in = name_func[i][0]
            name_out = name_func[i][1]
    
            if "boneFunction" not in obj[i].keys():
                obj[i].name = "bonefunction_%03d"%int(name_out)
            else:
                bpy.data.armatures[Armature_Name].bones.active = bpy.data.armatures[Armature_Name].bones[name_in]   
                bpy.ops.wm.properties_remove(data_path="active_bone", property_name="boneFunction")  
                child_id = bpy.data.armatures[Armature_Name].bones[name_in]["child"]
                child_id = "Bone.%03d"%child_id
                for j in range(len(obj)):
                    if name_func[j][0] == child_id:
                        bpy.data.armatures[Armature_Name].bones[name_in]["child"] = int(name_func[j][1])               
                obj[i].name = "bonefunction_%03d"%int(name_out)
        if options["Split Weights"] == "Group":
            for k in bpy.context.selected_objects:
                if k.type == "MESH":
                    k.modifiers[0].object = None
                    k.modifiers[0].object = bpy.context.active_object
        else: 
            bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
            for i in range(len(obj)):
                name_func[i][0] = name_func[i][0].replace("Bone.","")
            #print(name_func)    
            for obj in bpy.context.selected_objects:
                v_groups = obj.vertex_groups
                #for i in range(len(v_groups)):
                    #v_groups[i].name = v_groups[i].name.replace("Bone.","bonefunction_")
                for i in range(len(v_groups)):
                    for n in name_func:
                        if n[0] in v_groups[i].name:
                            v_groups[i].name = v_groups[i].name.replace("Bone.","bonefunction_")
                            v_groups[i].name = v_groups[i].name.replace(n[0],n[1])
                            break 
                        else:
                            continue
                for i in range(len(v_groups)):
                    v_groups[i].name = v_groups[i].name.replace(".001","")
            #bpy.ops.object.select_pattern(pattern=Armature_Name, case_sensitive=False, extend=True)      
        
        bpy.context.active_object.scale = (0.010,0.010,0.010)
        bpy.context.active_object.rotation_euler = (1.5708,0,0)          
        return {'FINISHED'}
    
    def parseOptions(self):
        options = {}
        if self.clear_scene:
            options["Clear"]=True
        if self.maximize_clipping:
            options["Max Clip"]=True
        if self.high_lod:
            options["High LOD"]=True
        if self.import_header:
            options["Scene Header"]=True
        if self.import_skeleton != "None":
            options["Skeleton"]=self.import_skeleton
        if self.import_meshparts:
            options["Mesh Parts"]=True
        if self.import_unknown_mesh_props:
            options["Mesh Unknown Properties"]=True
        if self.high_lod:
            options["Only Highest LOD"]=True
        if self.import_skeleton != "None" and self.import_meshparts and self.weight_format == "Group":
            if not self.independent_skeleton or self.import_skeleton != "EmptyTree":
                options["Skeleton Modifier"]= self.import_skeleton
        if self.import_textures:
            options["Import Textures"]=self.texture_path
        if self.override_defaults:
            options["Override Defaults"]=self.texture_path
        options["Split Weights"]=self.weight_format
        return options
    
def menu_func_import(self, context):
    self.layout.operator(ImportMOD3.bl_idname, text="MHW MOD3 (.mod3)")
