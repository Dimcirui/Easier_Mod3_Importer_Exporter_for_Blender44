# -*- coding: utf-8 -*-
"""
Created on Sun Mar 31 03:11:30 2019

@author: AsteriskAmpersand
Modified for Blender 4.4 compatibility - Fixed use_auto_smooth issue
"""

import bpy
import bmesh
import array
import os
from mathutils import Vector, Matrix
from collections import OrderedDict
try:
    from ..mod3.ModellingApi import ModellingAPI, debugger
    from ..blender import BlenderSupressor
    from ..blender.BlenderNormals import normalize
except:
    import sys
    sys.path.insert(0, r'..\mod3')
    from ModellingApi import ModellingAPI, debugger
    
def processPath(path):
    return os.path.splitext(os.path.basename(path))[0]

class BoneGraph():
    def __init__(self, armature):
        self.bones = {}
        self.boneParentage = {}
        for ix, bone in enumerate(armature):
            bonePoint = BonePoint("Bone.%03d"%ix, bone)
            self.bones[ix] = bonePoint 
            if bone["parentId"] in self.bones:
                self.bones[bone["parentId"]].children.append(bonePoint)
            else:
                if bone["parentId"] not in self.boneParentage:
                    self.boneParentage[bone["parentId"]]=[]
                self.boneParentage[bone["parentId"]].append(bonePoint)
        for parentId in self.boneParentage:
            if parentId != 255:
                self.bones[parentId].children += self.boneParentage[parentId]
        self.roots = self.boneParentage[255]
        
    def root(self):
        return self.roots
    
class BonePoint():
    def __init__(self, name, bone):
        self.properties = bone["CustomProperties"]
        self.name = name
        self.lmatrix = BlenderImporterAPI.deserializeMatrix("LMatCol",bone)
        self.pos = Vector((bone["x"],bone["y"],bone["z"]))
        self.children = []
    def children(self):
        return self.children

class BlenderImporterAPI(ModellingAPI):
    MACHINE_EPSILON = 2**-8
    dbg = debugger()
    
#=============================================================================
# Main Importer Calls
# =============================================================================
       
    @staticmethod
    def setScene(scene_properties, context):
        BlenderImporterAPI.parseProperties(scene_properties,bpy.context.scene.__setitem__)
    
    @staticmethod   
    def setMeshProperties(meshProperties, context):
        BlenderImporterAPI.parseProperties(meshProperties,bpy.context.scene.__setitem__)
      
    @staticmethod
    def createEmptyTree(armature, context):
        miniscene = OrderedDict()
        BlenderImporterAPI.createRootNub(miniscene)
        for ix, bone in enumerate(armature):
            if "Bone.%03d"%ix not in miniscene:
                BlenderImporterAPI.createNub(ix, bone, armature, miniscene)
        miniscene["Bone.%03d"%255].name = '%s Armature'%processPath(context.path)
        BlenderImporterAPI.linkChildren(miniscene)
        context.armature = miniscene
        return   
    
    @staticmethod
    def createArmature(armature, context):#Skeleton
        filename = processPath(context.path)
        BlenderImporterAPI.dbg.write("Loading Armature\n")
        bpy.ops.object.select_all(action='DESELECT')
        blenderArmature = bpy.data.armatures.new('%s Armature'%filename)
        arm_ob = bpy.data.objects.new('%s Armature'%filename, blenderArmature)
        bpy.context.collection.objects.link(arm_ob)
        bpy.context.evaluated_depsgraph_get().update()
        arm_ob.select_set(True)
        arm_ob.show_in_front = True
        bpy.context.view_layer.objects.active = arm_ob
        blenderArmature.display_type = 'STICK'
        bpy.ops.object.mode_set(mode='EDIT')
        
        empty = BlenderImporterAPI.createParentBone(blenderArmature)
        if len(armature) != 0:
            boneGraph = BoneGraph(armature)
            for bone in boneGraph.root():
                root = BlenderImporterAPI.createBone(blenderArmature, bone)
                root.parent = empty
                #arm.pose.bones[ix].matrix
            
        bpy.ops.object.editmode_toggle()
        BlenderImporterAPI.dbg.write("Loaded Armature\n")
        context.armature = arm_ob
        return
    
    @staticmethod
    def createMeshParts(meshPartList, context):
        meshObjects = []
        filename = processPath(context.path)
        bpy.ops.object.select_all(action='DESELECT')
        BlenderImporterAPI.dbg.write("Creating Meshparts\n")
        #blenderMeshparts = []
        for ix, meshpart in enumerate(meshPartList):
            BlenderImporterAPI.dbg.write("\tLoading Meshpart %d\n"%ix)
            #Geometry
            BlenderImporterAPI.dbg.write("\tLoading Geometry\n")
            blenderMesh, blenderObject = BlenderImporterAPI.createMesh("%s %03d"%(filename,ix),meshpart)
            BlenderImporterAPI.parseProperties(meshpart["properties"], blenderMesh.__setitem__)
            BlenderImporterAPI.dbg.write("\tBasic Face Count %d\n"%len(meshpart["faces"]))
            #Weight Handling
            BlenderImporterAPI.dbg.write("\tLoading Weights\n")
            BlenderImporterAPI.writeWeights(blenderObject, meshpart)
            #Normals Handling
            BlenderImporterAPI.dbg.write("\tLoading Normals\n")
            BlenderImporterAPI.setNormals(meshpart["normals"],blenderMesh)
            #Colour
            #Needs to enter object mode
            if meshpart["colour"]:
                BlenderImporterAPI.dbg.write("\tLoading Colours\n")
                vcol_layer = blenderMesh.vertex_colors.new()
                for l,col in zip(blenderMesh.loops, vcol_layer.data):
                    col.color = BlenderImporterAPI.mod3ToBlenderColour(meshpart["colour"][l.vertex_index])
            #UVs
            BlenderImporterAPI.dbg.write("\tLoading UVs\n")
            for ix, uv_layer in enumerate(meshpart["uvs"]):
                uvLayer = BlenderImporterAPI.createTextureLayer("UV%d"%ix, blenderMesh, uv_layer)#BlenderImporterAPI.uvFaceCombination(uv_layer, meshpart["faces"]))
                uvLayer.active = ix == 0
                BlenderImporterAPI.dbg.write("\tLayer Activated\n")
            BlenderImporterAPI.dbg.write("\tMeshpart Loaded\n")
            blenderMesh.update()
            meshObjects.append(blenderObject)
        context.meshes = meshObjects
        BlenderImporterAPI.dbg.write("Meshparts Created\n")

    @staticmethod
    def clearSelection():
        for ob in bpy.context.selected_objects:
            ob.select = False
     
    @staticmethod
    def linkEmptyTree(context):
        BlenderImporterAPI.clearSelection()
        armature = context.armature
        for ob in context.meshes:
            for bone in armature:
                modifier = ob.modifiers.new(name = armature[bone].name, type='HOOK')
                modifier.object = armature[bone]
                modifier.vertex_group = armature[bone].name
                modifier.falloff_type = "NONE"
                if not modifier.vertex_group:
                    ob.modifiers.remove(modifier)
                else:
                    bpy.context.scene.objects.active = ob
                    ob.select = True
                    bpy.ops.object.mode_set(mode = 'EDIT')
                    bpy.ops.object.hook_reset(modifier = armature[bone].name)
                    bpy.ops.object.mode_set(mode = 'OBJECT')
                    ob.select = False
                    bpy.context.scene.objects.active = None

    @staticmethod
    def linkArmature(context):
        with BlenderSupressor.SupressBlenderOps():
            for mesh in context.meshes:
                modifier = mesh.modifiers.new(name = "", type='ARMATURE')
                modifier.object = context.armature
                bpy.ops.object.select_pattern(pattern=mesh.name, case_sensitive=False, extend=True)
        bpy.ops.object.select_pattern(pattern=context.armature.name, case_sensitive=False, extend=True)
        bpy.context.view_layer.objects.active = bpy.data.objects[context.armature.name]
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
        #bpy.ops.object.select_all(action='DESELECT')

        
    @staticmethod
    def clearScene(context):
        BlenderImporterAPI.dbg.write("Clearing Scene\n")
        for key in list(bpy.context.scene.keys()):
            del bpy.context.scene[key]
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete() 
        for i in bpy.data.images.keys():
            bpy.data.images.remove(bpy.data.images[i])
        BlenderImporterAPI.dbg.write("Scene Cleared\n")
        return
    
    @staticmethod
    def importTextures(textureFetch, context):
        BlenderImporterAPI.dbg.write("Importing Texture\n")
        if not textureFetch:
            BlenderImporterAPI.dbg.write("Failed to Import Texture\n")
            return
        BlenderImporterAPI.dbg.write("\tIterating over Meshes\n")
        for meshObject in context.meshes:
            try:
                BlenderImporterAPI.dbg.write("\t%s\n"%meshObject.name)
                BlenderImporterAPI.dbg.write("\tGetting Material Code\n")
                materialStr = meshObject.data['material'].replace('\x00','')
                BlenderImporterAPI.dbg.write("\tFetching Material from MRL3\n")
                BlenderImporterAPI.dbg.write("\t%s\n"%materialStr)
                filepath = textureFetch(materialStr)
                BlenderImporterAPI.dbg.write("\tFetching File\n")
                textureData = BlenderImporterAPI.fetchTexture(filepath)
                BlenderImporterAPI.dbg.write("\tAssigning Texture to Model\n")
                BlenderImporterAPI.assignTexture(meshObject, textureData)
                BlenderImporterAPI.dbg.write("\tAssigned Texture to Model\n")
            except Exception as e:
                pass
            
    @staticmethod       
    def overrideMeshDefaults(context):
        if context.meshes:
            BlenderImporterAPI.setWorldMeshDefault((context.meshes[0].data))
        
    @staticmethod
    def maximizeClipping(context):
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                for s in a.spaces:
                    if s.type == 'VIEW_3D':
                        s.clip_end = 10**9
                        
# =============================================================================
# Helper Methods
# =============================================================================
    @staticmethod
    def parseProperties(properties, assignmentFunction):
        for name, val in sorted(properties.items(), key=lambda x: x[0]):
            assignmentFunction(name,val)
    
    @staticmethod
    def tupleSum(t1,t2):
        return tuple((i+j for i,j in zip(t1,t2)))
    
    @staticmethod
    def normalize(vector):
        factor = sum([v*v for v in vector])
        if not factor:
            return Vector(vector)
        return Vector([v/factor for v in vector])
        

# =============================================================================
# Mesh Handling
# =============================================================================
    
    @staticmethod
    def createMesh(name, meshpart):
        BlenderImporterAPI.dbg.write("Geometry Construction\n")
        blenderMesh = bpy.data.meshes.new("%s LOD %d"%(name,meshpart["properties"]["lod"]))
        BlenderImporterAPI.dbg.write("Geometry From Pydata\n")
        BlenderImporterAPI.dbg.write("Vertex Count: %d\n"%len(meshpart['vertices']))
        BlenderImporterAPI.dbg.write("Faces %d %d\n"%(min(map(lambda x: min(x,default=0),meshpart["faces"]),default=0), max(map(lambda x: max(x,default=0),meshpart["faces"]),default=0)))
        blenderMesh.from_pydata(meshpart["vertices"],[],meshpart["faces"])
        BlenderImporterAPI.dbg.write("Pydata Loaded\n")
        blenderMesh.update()
        blenderObject = bpy.data.objects.new("%s LOD %d"%(name,meshpart["properties"]["lod"]), blenderMesh)
        BlenderImporterAPI.dbg.write("Geometry Link\n")
        bpy.context.collection.objects.link(blenderObject)
        return blenderMesh, blenderObject
    
    @staticmethod
    def setNormals(normals, meshpart):
        """Set custom normals - Blender 4.4 compatible version"""
        meshpart.update(calc_edges=True)
        #meshpart.normals_split_custom_set_from_vertices(normals)
        
        clnors = array.array('f', [0.0] * (len(meshpart.loops) * 3))
        meshpart.loops.foreach_get("normal", clnors)
        meshpart.polygons.foreach_set("use_smooth", [True] * len(meshpart.polygons))
        
        #meshpart.normals_split_custom_set(tuple(zip(*(iter(clnors),) * 3)))
        meshpart.normals_split_custom_set_from_vertices([normalize(v) for v in normals])
        #meshpart.normals_split_custom_set([normals[loop.vertex_index] for loop in meshpart.loops])
        
        # IMPORTANT: In Blender 4.1+, use_auto_smooth has been removed
        # The custom normals are already set above, which is sufficient
        # DO NOT try to access meshpart.use_auto_smooth
        
        # Note: bpy.types.View3DOverlay.show_edge_sharp is a UI preference, not a mesh property
        # It affects all meshes in the viewport, so we skip it to avoid side effects
        
        #db
    
    @staticmethod
    def normalCheck(meshpart):
        normals = {}
        for l in meshpart.loops:
            if l.vertex_index in normals and l.normal != normals[l.vertex_index]:
                raise "Normal Abortion"
            else:
                normals[l.vertex_index]=l.normal
        
    @staticmethod
    def mod3ToBlenderColour(mod3Colour):
        return (mod3Colour.Red/255.0,mod3Colour.Green/255.0,mod3Colour.Blue/255.0,mod3Colour.Alpha/255.0)
    
    @staticmethod
    def setWorldMeshDefault(mesh):
        BlenderImporterAPI.parseProperties({"DefaultMesh-"+prop:mesh[prop] for prop in ModellingAPI.MeshDefaults},bpy.context.scene.__setitem__)
            

# =============================================================================
# Skeleton Methods
# =============================================================================
        
    MTFCormat = Matrix([[0,1,0,0],
                      [-1,0,0,0],
                      [0,0,1,0],            
                      [0,0,0,1]])
    
    @staticmethod
    def createRootNub(miniscene):
        o = bpy.data.objects.new("Bone.%03d"%255, None )
        miniscene["Bone.%03d"%255]=o
        bpy.context.collection.objects.link( o )
        o.show_wire = True
        o.show_in_front = True
        return
        
    
    @staticmethod
    def createNub(ix, bone, armature, miniscene):
        o = bpy.data.objects.new("Bone.%03d"%ix, None )
        miniscene["Bone.%03d"%ix]=o
        bpy.context.collection.objects.link( o )
        #if bone["parentId"]!=255:
        parentName = "Bone.%03d"%bone["parentId"]
        if parentName not in miniscene:
            BlenderImporterAPI.createNub(bone["parentId"],armature[bone["parentId"]],miniscene)
        o.parent = miniscene[parentName]
        
        o.matrix_local = BlenderImporterAPI.deserializeMatrix("LMatCol",bone)
        o.show_wire = True
        o.show_in_front = True
        o.show_bounds = True
        BlenderImporterAPI.parseProperties(bone["CustomProperties"],o.__setitem__)
    
    class DummyBone():
        def __init__(self):
            self.matrix = Matrix.Identity(4)
            self.head = Vector([0,-1,0])
            self.tail = Vector([0,0,0])
            self.magnitude = 1
            
    @staticmethod
    def createParentBone(armature):
        bone = armature.edit_bones.new("Bone.255")
        bone.head = Vector([0, 0, 0])
        bone.tail = Vector([0, BlenderImporterAPI.MACHINE_EPSILON, 0])
        bone.matrix = Matrix.Identity(4)        
        return bone
        
    @staticmethod
    def createBone(armature, obj, parent_bone = None):
        bone = armature.edit_bones.new(obj.name)
        bone.head = Vector([0, 0, 0])
        bone.tail = Vector([0, BlenderImporterAPI.MACHINE_EPSILON, 0])#Vector([0, 1, 0])
        if not parent_bone:
            parent_bone = BlenderImporterAPI.DummyBone()#matrix = Identity(4), #boneTail = 0,0,0, boneHead = 0,1,0
        bone.matrix = parent_bone.matrix @ obj.lmatrix
        for child in obj.children:
            nbone = BlenderImporterAPI.createBone(armature, child, bone)
            nbone.parent = bone
        BlenderImporterAPI.parseProperties(obj.properties,bone.__setitem__)
        return bone
    
    @staticmethod
    def deserializeMatrix(baseString, properties):
        matrix = Matrix(list(map(list,zip(*[properties[baseString+"%d"%column] for column in range(4)]))))
        return matrix
    
    @staticmethod
    def writeWeights(blenderObject, mod3Mesh):
        for groupIx,group in mod3Mesh["weightGroups"].items():
            groupId = "%03d"%groupIx if isinstance(groupIx, int) else str(groupIx) 
            groupName = "Bone.%s"%str(groupId)
            for vertex,weight in group:
                if groupName not in blenderObject.vertex_groups:
                    blenderObject.vertex_groups.new(name = groupName)#blenderObject Maybe?
                blenderObject.vertex_groups[groupName].add([vertex], weight, 'ADD')
            bpy.ops.object.select_pattern(pattern=blenderObject.name, case_sensitive=False, extend=True)
        return
    
    @staticmethod
    def linkChildren(miniscene):
        for ex in range(len(miniscene)-1):
            e = miniscene["Bone.%03d"%ex]
            if e["child"] != 255:
                c = e.constraints.new('CHILD_OF')
                for prop in ["location","rotation","scale"]:
                    for axis in ["x","y","z"]:
                        c.__setattr__("use_%s_%s"%(prop,axis), False)
                c.target=miniscene["Bone.%03d"%e["child"]]
                c.active=False
            del e["child"]
    
# =============================================================================
# UV and Texture Handling
# =============================================================================
             
    @staticmethod
    def fetchTexture(filepath):
        filepath = filepath+".png"
        BlenderImporterAPI.dbg.write("\t%s\n"%filepath)
        if os.path.exists(filepath):
            return bpy.data.images.load(filepath)
        else:
            raise FileNotFoundError("File %s not found"%filepath)
    
    @staticmethod
    def assignTexture(meshObject, textureData):
        for uvLayer in meshObject.data.uv_textures:
            for uv_tex_face in uvLayer.data:
                uv_tex_face.image = textureData
        meshObject.data.update()
        
    @staticmethod
    def createTextureLayer(name, blenderMesh, uv):#texFaces):
        #if bpy.context.active_object.mode!='OBJECT':
        #    bpy.ops.object.mode_set(mode='OBJECT')
        BlenderImporterAPI.dbg.write("\t\tCreating new UV\n")
        blenderMesh.uv_layers.new(name = name)
        blenderMesh.update()
        BlenderImporterAPI.dbg.write("\t\tCreating BMesh\n")
        blenderBMesh = bmesh.new()
        blenderBMesh.from_mesh(blenderMesh)
        BlenderImporterAPI.dbg.write("\t\tAcquiring UV Layer\n")
        uv_layer = blenderBMesh.loops.layers.uv[name]
        blenderBMesh.faces.ensure_lookup_table()
        BlenderImporterAPI.dbg.write("\t\tBMesh Face Count %d\n"%len(blenderBMesh.faces))
        BlenderImporterAPI.dbg.write("\t\tStarting Looping\n")
        BlenderImporterAPI.dbg.write("\t\tUV Vertices Count %d\n"%len(uv))
        for face in blenderBMesh.faces:
            for loop in face.loops:
                #BlenderImporterAPI.dbg.write("\t%d\n"%loop.vert.index)
                loop[uv_layer].uv = uv[loop.vert.index]
        BlenderImporterAPI.dbg.write("\t\tUVs Edited\n") 
        blenderBMesh.to_mesh(blenderMesh)
        BlenderImporterAPI.dbg.write("\t\tMesh Written Back\n")
        blenderMesh.update()
        BlenderImporterAPI.dbg.write("\t\tMesh Updated\n")
        return blenderMesh.uv_layers[name]
    
    @staticmethod
    def uvFaceCombination(vertexUVMap, FaceList):
        BlenderImporterAPI.dbg.write("\t\tFaces %d %d - UV Count %d\n"%(min(map(min,FaceList)), max(map(max,FaceList)), len(vertexUVMap)))
        #BlenderImporterAPI.dbg.write("UVs %s\n"%str([list(map(lambda x: vertexUVMap[x], face)) for face in FaceList]))
        return sum([list(map(lambda x: vertexUVMap[x], face)) for face in FaceList],[])