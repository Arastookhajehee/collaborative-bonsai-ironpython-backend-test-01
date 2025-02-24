import Rhino.Geometry as rg
import math

def plane_from_csv(csv):
    parts = csv.split(',')
    pnt = rg.Point3d(float(parts[0]),float(parts[1]),float(parts[2]))
    vec1 = rg.Vector3d(float(parts[3]),float(parts[4]),float(parts[5]))
    vec2 = rg.Vector3d(float(parts[6]),float(parts[7]),float(parts[8]))

    return rg.Plane(pnt,vec1,vec2)

def PlaneToStick(placementPlane):
    width = 18;
    length = 300;
    thickness = 18;
    xInterval = rg.Interval(-width / 2, width / 2);
    yInterval = rg.Interval(-length / 2, length / 2);
    zInterval = rg.Interval(-thickness / 2, thickness / 2);
    stick = rg.Box(placementPlane, xInterval, yInterval, zInterval).ToBrep();
    return stick

def StickToPlane(stick):
    sorted_faces = SortStickFaces(stick)
    sides = GetSides(sorted_faces)
    tips = GetTips(sorted_faces)
    stick_plane = GetStickPlane(sides, tips)
    rotated_stick_plane = rg.Plane(stick_plane.Origin, stick_plane.XAxis, stick_plane.ZAxis)
    return rotated_stick_plane

def ScaleLine(line, factor):
    linevec = rg.Vector3d(line[1]-line[0])
    linemid = (line[0]+line[1])/2
    lineplane = rg.Plane(linemid,rg.Plane.WorldXY.ZAxis)
    line.Transform(rg.Transform.Scale(lineplane,factor,factor,factor))

def SortStickFaces(stick):
    faces = stick.Faces
    areas=[rg.AreaMassProperties.Compute(face).Area for face in faces]
    faces_and_areas = zip(faces,areas)
    sorted_faces = sorted(faces_and_areas, key=lambda x: x[1])
    return sorted_faces

def GetSides(sorted_faces):
    sides = [face[0] for face in sorted_faces[2:]]
    return sides

def GetTips(sorted_faces):
    tips = [face[0] for face in sorted_faces[:2]]
    return tips

def GetThickness(tips):
    area = rg.AreaMassProperties.Compute(tips[0]).Area
    thickness = math.sqrt(area)
    return thickness

def GetLength(tips):
    top = rg.AreaMassProperties.Compute(tips[0]).Centroid
    bottom = rg.AreaMassProperties.Compute(tips[1]).Centroid
    length = top.DistanceTo(bottom)
    return length

def GetStickPlane(sides, tips):
    top = rg.AreaMassProperties.Compute(tips[0]).Centroid
    bottom = rg.AreaMassProperties.Compute(tips[1]).Centroid
    center = (top+bottom)/2
    z_axis = rg.Vector3d(top-bottom)
    x_axis = sides[0].NormalAt(0,0)
    y_axis = rg.Vector3d.CrossProduct(z_axis, x_axis)
    plane = rg.Plane(center,x_axis,y_axis)
    return plane

def GetSidePlane(sides, side_id, stick_plane):
    side = sides[side_id]
    center = rg.AreaMassProperties.Compute(side).Centroid
    x_axis = stick_plane.ZAxis
    z_axis = side.NormalAt(0,0)
    y_axis = rg.Vector3d.CrossProduct(z_axis, x_axis)
    plane = rg.Plane(center,x_axis,y_axis)
    return plane

def GetSharedPlane(side_plane_a, side_plane_b, shift_ab):
    shared_line = rg.Intersect.Intersection.PlanePlane(side_plane_a,side_plane_b)[1]
    ScaleLine(shared_line,100)
    shared_vector = rg.Vector3d(shared_line[1]-shared_line[0])
    shared_vector.Unitize()
    shared_line = shared_line.ToNurbsCurve()
    shared_line.Domain = rg.Interval(0,1)
    shared_plane = rg.Plane(shared_line.PointAt(shift_ab),shared_vector)
    return shared_plane
    
def GetSharedLine(side_plane_a, side_plane_b, shift_ab):
    shared_line = rg.Intersect.Intersection.PlanePlane(side_plane_a,side_plane_b)[1]
    ScaleLine(shared_line,100)
    shared_vector = rg.Vector3d(shared_line[1]-shared_line[0])
    shared_vector.Unitize()
    shared_line = shared_line.ToNurbsCurve()
    shared_line.Domain = rg.Interval(0,1)
    return shared_line

def CreateNewStick(stick, stick_plane, side_plane, shared_plane, shared_line, thickness, length, flip, shift):
    line = rg.Intersect.Intersection.PlanePlane(shared_plane,side_plane)[1]
    ScaleLine(line,100)
    overlap = rg.Intersect.Intersection.CurveBrep(line.ToNurbsCurve(),stick,0.0001)[1]
    if len(overlap)>0:
        point = (overlap[0].PointAtStart+overlap[0].PointAtEnd)/2
    else: point = (line[0]+line[1])/2
    point = (point+shared_plane.Origin)/2
    vector = rg.Vector3d(shared_line.PointAtEnd-shared_line.PointAtStart)
    new_stick_plane = rg.Plane(point,vector,side_plane.ZAxis)
    new_stick = stick.Duplicate()
    new_stick.Transform(rg.Transform.PlaneToPlane(stick_plane,new_stick_plane))
    new_stick.Transform(rg.Transform.Translation(thickness/2*new_stick_plane.YAxis))
    new_stick.Transform(rg.Transform.Translation(flip*thickness/2*shared_plane.ZAxis))
    new_stick.Transform(rg.Transform.Translation(length*shift*new_stick_plane.ZAxis))
    return new_stick

def AdjustP1(sides,side_id,shared_plane):
    face = sides[side_id]
    edge = face.OuterLoop.To3dCurve()
    segments = edge.DuplicateSegments()
    vertices = [segment.PointAtStart for segment in segments]
    distances = [vertice.DistanceTo(rg.Plane.ClosestPoint(shared_plane, vertice)) for vertice in vertices]
    return (min(distances), max(distances))

def GenerateLink(stick_a,stick_b,side_id_a,side_id_b, shift_ab, flip, shift_a, shift_b):

    # Get Planes
    sorted_faces_a = SortStickFaces(stick_a)
    sides_a = GetSides(sorted_faces_a)
    tips_a = GetTips(sorted_faces_a)
    sorted_faces_b = SortStickFaces(stick_b)
    sides_b = GetSides(sorted_faces_b)
    tips_b = GetTips(sorted_faces_b)
    thickness_a = GetThickness(tips_a)
    length_a = GetLength(tips_a)
    thickness_b = GetThickness(tips_b)
    length_b = GetLength(tips_b)
    stick_plane_a = GetStickPlane(sides_a, tips_a)
    center_a = stick_plane_a.Origin
    stick_plane_b = GetStickPlane(sides_b, tips_b)
    center_b = stick_plane_b.Origin
    side_plane_a = GetSidePlane(sides_a, side_id_a, stick_plane_a)
    side_plane_b = GetSidePlane(sides_b, side_id_b, stick_plane_b)
    temp=(side_plane_a,side_plane_b)
    
    shared_plane = GetSharedPlane(side_plane_a, side_plane_b, 0)
    shared_line = GetSharedLine(side_plane_a, side_plane_b, 0)

    # Adjust P1
    min_distance_a = AdjustP1(sides_a,side_id_a,shared_plane)[0]
    max_distance_a = AdjustP1(sides_a,side_id_a,shared_plane)[1]
    min_distance_b = AdjustP1(sides_b,side_id_b,shared_plane)[0]
    max_distance_b = AdjustP1(sides_b,side_id_b,shared_plane)[1]
    min_distance = max((min_distance_a, min_distance_b))
    max_distance = min((max_distance_a, max_distance_b))
    translation = shift_ab*min_distance+(1-shift_ab)*max_distance
    shared_plane.Translate(translation*shared_plane.ZAxis)

    # Create sticks
    if flip is True: flip = 1
    else: flip = -1
    stick_c = CreateNewStick(stick_a, stick_plane_a, side_plane_a, shared_plane, shared_line, thickness_a, length_a, flip, shift_a)
    stick_d = CreateNewStick(stick_b, stick_plane_b, side_plane_b, shared_plane, shared_line, thickness_b, length_b, -flip, shift_b)
    #return stick_c, stick_d, shared_line, stick_line_c, stick_line_d
    return (stick_c, stick_d)

def process_planes(branch_a, branch_b, shift_ab, shift_a, shift_b):
    vec1 = branch_a.ZAxis
    vec2 = branch_b.ZAxis
    errors_txt = []
    #print vec1.IsParallelTo(vec2, 0.01)
    #print vec1.IsPerpendicularTo(vec2, 0.01)
    #if vec1.IsParallelTo(vec2, 0.01) == 0 or vec1.IsPerpendicularTo(vec2, 0.01) is False:
    stick_a = PlaneToStick(branch_a)
    stick_b = PlaneToStick(branch_b)
    sorted_faces_a = SortStickFaces(stick_a)
    sides_a = GetSides(sorted_faces_a)
    tips_a = GetTips(sorted_faces_a)
    thickness_a = GetThickness(tips_a)
    length_a = GetLength(tips_a)
    min_glue_area = thickness_a**2
    configurations = []
    for i in range(4): # 4 sides_a
        for j in range(4): # 4 sides_b
            for k in [True, False]: # flip = True or False
                try:
                    configurations.append(GenerateLink(stick_a,stick_b,i,j, shift_ab, k, shift_a, shift_b))
                except:
                    configurations.append(None)
    valid_configurations = []
    other_configurations = []
    valid_ids = []
    n=0
    for configuration in configurations:
        if configuration != None:
            stick_c, stick_d = configuration[0:2]
            temp = stick_c, stick_d
            flag = False
            if len(rg.Intersect.Intersection.BrepBrep(stick_a, stick_d, 0.001)[1]) == 0:
                if len(rg.Intersect.Intersection.BrepBrep(stick_b, stick_c, 0.001)[1]) == 0:
                    if len(rg.Intersect.Intersection.BrepBrep(stick_c, stick_d, 0.001)[1]) > 0:
                        if len(rg.Intersect.Intersection.BrepBrep(stick_a, stick_c, 0.001)[1]) > 0:
                            if len(rg.Intersect.Intersection.BrepBrep(stick_b, stick_d, 0.001)[1]) > 0:
                                cd = rg.Brep.CreatePlanarBreps(rg.Curve.JoinCurves(rg.Intersect.Intersection.BrepBrep(stick_c, stick_d, 0.001)[1]))
                                ac = rg.Brep.CreatePlanarBreps(rg.Curve.JoinCurves(rg.Intersect.Intersection.BrepBrep(stick_a, stick_c, 0.001)[1]))
                                bd = rg.Brep.CreatePlanarBreps(rg.Curve.JoinCurves(rg.Intersect.Intersection.BrepBrep(stick_b, stick_d, 0.001)[1]))
                                if cd is not None and ac is not None and bd is not None:
                                    if rg.AreaMassProperties.Compute(cd).Area > min_glue_area and rg.AreaMassProperties.Compute(ac).Area > min_glue_area and rg.AreaMassProperties.Compute(bd).Area > min_glue_area:
                                            valid_configurations.append(configuration)
                                            valid_ids.append(n)
                                            flag = True
                                            errors_txt.append(None)
                                    else: errors_txt.append("insufficient contact")
                                else: errors_txt.append("insufficient contact")
                            else: errors_txt.append("no contact")
                        else: errors_txt.append("no contact")
                    else: errors_txt.append("no contact")
                else: errors_txt.append("collision")
            else: errors_txt.append("collision")
            if flag is False:
                other_configurations.append(configuration)
        n+=1
    #else: errors_txt.append("Coplanar sticks...")
    return valid_configurations, configurations, valid_ids, errors_txt

def StickToPlane(stick):
    sorted_faces = SortStickFaces(stick)
    sides = GetSides(sorted_faces)
    tips = GetTips(sorted_faces)
    stick_plane = GetStickPlane(sides, tips)
    rotated_stick_plane = rg.Plane(stick_plane.Origin, stick_plane.XAxis, stick_plane.ZAxis)
    return rotated_stick_plane

def SortStickFaces(stick):
    faces = stick.Faces
    areas=[rg.AreaMassProperties.Compute(face).Area for face in faces]
    faces_and_areas = zip(faces,areas)
    sorted_faces = sorted(faces_and_areas, key=lambda x: x[1])
    return sorted_faces

def GetSides(sorted_faces):
    sides = [face[0] for face in sorted_faces[2:]]
    return sides

def GetTips(sorted_faces):
    tips = [face[0] for face in sorted_faces[:2]]
    return tips

def GetStickPlane(sides, tips):
    top = rg.AreaMassProperties.Compute(tips[0]).Centroid
    bottom = rg.AreaMassProperties.Compute(tips[1]).Centroid
    center = (top+bottom)/2
    z_axis = rg.Vector3d(top-bottom)
    x_axis = sides[0].NormalAt(0,0)
    y_axis = rg.Vector3d.CrossProduct(z_axis, x_axis)
    plane = rg.Plane(center,x_axis,y_axis)
    return plane

def process_sticks(run, only_valid, valid_configurations, configurations,valid_ids,errors_txt, browse):
    if run:
        #if errors_txt[0] != "Coplanar sticks...":
        if only_valid:
            if len(valid_configurations) > 0:
                browse = browse%len(valid_configurations)
                stick_c, stick_d = valid_configurations[browse]
                plane_c = StickToPlane(stick_c)
                plane_d = StickToPlane(stick_d)
                conf_id = "configuration number: "+ str(valid_ids[browse])
                return plane_c, plane_d
            else:
                conf_id = "no valid configurations"
                return None, None
        
        else:
            stick_c, stick_d = configurations[browse]
            plane_c = StickToPlane(stick_c)
            plane_d = StickToPlane(stick_d)
            return plane_c, plane_d
            print(errors_txt[browse])
        #else:
            #print(errors_txt[0])
            #plane_c=branch_a.placementPlane
            #plane_d=branch_b.placementPlane
    else:
        conf_id = "please select two sticks"

def csv_from_plane(plane01):
    plane01csv = str.format(
        "{},{},{},{},{},{},{},{},{}",
        plane01.Origin.X, 
        plane01.Origin.Y, 
        plane01.Origin.Z, 
        plane01.XAxis.X, 
        plane01.XAxis.Y, 
        plane01.XAxis.Z, 
        plane01.YAxis.X, 
        plane01.YAxis.Y, 
        plane01.YAxis.Z, 
    )
    return plane01csv

def process_bridge(branch_a_csv, branch_b_csv, shift_ab= -4.95, shift_a = 0.146, shift_b= -0.186,browse = 2,only_valid = False)
    branch_a = plane_from_csv(branch_a_csv)
    branch_b = plane_from_csv(branch_b_csv)
    valid_configurations, configurations, valid_ids, errors_txt = process_planes(branch_a, branch_b, shift_ab, shift_a, shift_b)
    plane_c, plane_d = process_sticks(True, only_valid, valid_configurations, configurations,valid_ids,errors_txt, browse)
    
    return csv_from_plane(plane_c), csv_from_plane(plane_d)