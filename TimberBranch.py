import clr
import System
import Rhino
import math
from System import Guid
from System.Drawing import Color
from Rhino.Geometry import Plane, Mesh, Box, Interval, Rectangle3d, Transform, Brep, MeshingParameters

# Newtonsoft dll is in the same folder
import os
clr.AddReference('Newtonsoft.Json.dll')
from Newtonsoft.Json import JsonConvert

class TimberBranch:
    def __init__(self, placement_plane=None, user=None, color=None, state=None, branch=None, parentIDs=None):
        try:
            self.ID = Guid.NewGuid()
            self.placementPlane = placement_plane if placement_plane else Plane.WorldXY
            self.duplicatePlane = Plane(self.placementPlane)
            self.buildOnPlane = Plane(self.placementPlane)
            self.orientablePlanes = []
            self.meshBox = Mesh()
            self.user = user
            self.color = color
            self.state = state
            self.parentIDs = parentIDs if parentIDs else []
            self.childIDs = []
            self.width = 18.0
            self.length = 300.0
            self.thickness = 18.0
            self.designTimeStamp = TimberBranch.GetTimeStamp()
            self.modificationTimeStamp = ""
            self.physicalTimeStamp = ""
            self.brep = None
            self.selected = False
            self.message = ""
            self.fabricatedTimeStamp = ""
            self.fabricationFail = False
            self.placementGlueShift = ""
            self.placementShift = ""
            
            if branch:
                self.copy_from(branch, placement_plane)
            else:
                self.create_brep()
                self.create_planes_and_mesh()
        except:
            self.ID = Guid.Empty

    def copy_from(self, branch, placement_plane):
        self.ID = branch.ID
        self.placementPlane = placement_plane
        self.duplicatePlane = Plane(placement_plane)
        self.buildOnPlane = Plane(placement_plane)
        self.orientablePlanes = []
        self.meshBox = Mesh()
        self.user = branch.user
        self.color = branch.color
        self.state = branch.state
        self.parentIDs = branch.parentIDs[:]
        self.childIDs = branch.childIDs[:]
        self.width = branch.width
        self.length = branch.length
        self.thickness = branch.thickness
        self.designTimeStamp = branch.designTimeStamp
        self.modificationTimeStamp = TimberBranch.GetTimeStamp()
        self.create_brep()
        self.create_planes_and_mesh()

    def create_brep(self):
        x_interval = Interval(-self.width / 2, self.width / 2)
        y_interval = Interval(-self.length / 2, self.length / 2)
        z_interval = Interval(-self.thickness / 2, self.thickness / 2)
        self.brep = Box(self.placementPlane, x_interval, y_interval, z_interval).ToBrep()

    def create_planes_and_mesh(self):
        tolerance = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
        planes = []
        for i in range(4):
            plane = Plane(self.placementPlane)
            plane.Rotate(i * math.pi / 2, self.placementPlane.YAxis, self.placementPlane.Origin)
            planes.append(plane)
            face_border = TimberBranch.GetBorderFace(plane, self.width, self.length, self.thickness)
            meshing_parameters = MeshingParameters()
            meshing_parameters.SimplePlanes = True
            meshing_parameters.GridMaxCount = 1
            border = face_border.ToNurbsCurve()
            self.meshBox.Append(Mesh.CreateFromPlanarBoundary(border, meshing_parameters, tolerance))
        self.orientablePlanes = planes

    def Select(self):
        self.selected = True
        self.color = Color.FromArgb(255, self.color.R, self.color.G, self.color.B)

    def UnSelect(self):
        self.selected = False
        self.color = Color.FromArgb(70, self.color.R, self.color.G, self.color.B)

    def AddParentID(self, parent_id):
        self.parentIDs.append(parent_id)

    def AddChildID(self, child_id):
        self.childIDs.append(child_id)

    def RemoveParentID(self, parent_id):
        self.parentIDs.remove(parent_id)

    def RemoveChildID(self, child_id):
        self.childIDs.remove(child_id)

    def ToJson(self):
        return JsonConvert.SerializeObject(self)

    @staticmethod
    def FromJson(json_str):
        return JsonConvert.DeserializeObject[TimberBranch](json_str)

    def BuildOn(self, user, color, state, ignore_heirarchy=False):
        plane = self.buildOnPlane
        new_branch = TimberBranch(plane, user, color, state)
        if ignore_heirarchy:
            return new_branch
        new_branch.AddParentID(self.ID)
        self.AddChildID(new_branch.ID)
        return new_branch

    @staticmethod
    def GetBorderFace(orientation_plane, width, length, thickness):
        x_interval = Interval(-width / 2, width / 2)
        y_interval = Interval(-length / 2, length / 2)
        rect = Rectangle3d(orientation_plane, x_interval, y_interval)
        rect.Transform(Transform.Translation(orientation_plane.ZAxis * -thickness / 2))
        return rect

    @staticmethod
    def GetTimeStamp():
        return System.DateTime.Now.ToString("yyyy-MM-dd-HH-mm-ss")

    @staticmethod
    def ListToJson(branch_list):
        return JsonConvert.SerializeObject(branch_list)

    @staticmethod
    def FromJsonToList(json_str):
        return JsonConvert.DeserializeObject[list](json_str)
