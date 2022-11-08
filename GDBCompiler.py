#-------------------------------------------------------------------------------
# Name:        GDBCompiler
# Purpose:     Compiles component maps and inserts a consistant boundary
#
# Author:      jrwinter
#
# Created:     20/11/2017
# Copyright:   (c) jrwinter 2017
# Licence:     <your licence>
# Version:     3.4


#----------------------Considerations and Specifications-------------------------#

    # In general data should be clean and ready to compile. You can try running on partially-complete GDBs but unexpected results are possible

    # SRC_SYM, FTYPE, and GMAP_ID, fields need to be fully populated. The tool relys on these fields for certain operations.

    # SYM field should be populated if you want the tool to symbolize internal quadrangle boundaries for you

    # The user can either input a boundary shapefile that they have previously created (recommended) or input a tics shapefile (in Decimal Degrees)
    # and specify the number of quads high and across

#---------------------------------Import system modules-----------------#

import sys, string, os, arcpy, arcgisscripting, shutil


#------------------Alters the SYM field for internal quad boundaries-------------#

expression1 = "getSym(str(!SYM!))"
codeblock1 = """
def getSym(sym):
    return sym[:5] + '.01' + sym[5:]
    """

#-------------Alters the NOTES field for internal quad and map boundaries------------#

expression2 = "getText(str(!NOTES!), !POS!)"
codeblock2 = """
def getText(notes, pos):
    if pos == 10:
        if str(notes) == "NA" or str(notes) == "" or str(notes) == "internal quadrangle boundary; source map indicated is one of two source maps":
            return "internal quadrangle boundary; source map indicated is one of two source maps"
        else:
            return notes + "; internal quadrangle boundary; source map indicated is one of two source maps"
    if pos == 11:
        if str(notes) == "NA" or str(notes) == "" or str(notes) == "internal map boundary; source map indicated is one of two source maps":
            return "internal map boundary; source map indicated is one of two source maps"
        else:
            return notes + "; internal map boundary; source map indicated is one of two source maps"
    """

#--------------------Pushes GMAP_IDs to quad boundaries---------------------#

expression3 = "getGMAP(!GMAP_ID!, !LEFT_GMAP_ID!, !RIGHT_GMAP_ID!)"
codeblock3 = """
def getGMAP(gmap, left, right):
    if left == 0:
        return right
    else:
        return left
    """
#-------------------Declares user inputs----------------------#

GDB_List = arcpy.GetParameterAsText(0).split(";")
Output_Location = arcpy.GetParameterAsText(1)
Park_Code = arcpy.GetParameterAsText(2)
mapType = arcpy.GetParameterAsText(3)
Boundary = arcpy.GetParameterAsText(4)
Input_Coordinate_System = arcpy.GetParameterAsText(5)
Trim_Extend_Length = arcpy.GetParameterAsText(6)
Create_Midpoints = arcpy.GetParameterAsText(7)
Map_Scale = arcpy.GetParameter(8)
Create_Topology = arcpy.GetParameterAsText(9)
topology = arcpy.GetParameterAsText(10)

if arcpy.Exists(Output_Location + "\\" + Park_Code + "_BEST_BOUNDARY.shp"):
    next
else:
    arcpy.Copy_management(Boundary, Output_Location + "\\" + Park_Code + "_BEST_BOUNDARY.shp")
#---------------Checks the user's Home Directory for scratch.gdb and deletes it if it exists----------------#

path = "~/scratch.gdb"
full_path = os.path.expanduser(path)
arcpy.AddMessage(full_path)
if arcpy.Exists(full_path):
    arcpy.Delete_management(full_path)

Compile_Geodatabase = Output_Location + "\\" + Park_Code + "_" + mapType + ".gdb"
if arcpy.Exists(Compile_Geodatabase):
    arcpy.AddMessage("Output GDB name can not be the same name as an input component map gdb. Delete or Rename: " + Park_Code + "_" + mapType + ".gdb")
    sys.exit()

#---------Creates a scratch.gdb in the user's Home Directory folder to work with----------#

arcpy.env.scratchWorkspace = full_path
memoryGDB = arcpy.env.scratchGDB
arcpy.CreateFeatureDataset_management(memoryGDB, Park_Code, Input_Coordinate_System)

for GDB in GDB_List:
    arcpy.env.workspace = GDB
    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        arcpy.env.workspace = GDB + "\\" + fd
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            describ = arcpy.Describe(fc)
            if arcpy.Exists(memoryGDB + "\\" + Park_Code + "\\" + Park_Code + fc[4:]):
                arcpy.Append_management(fc, memoryGDB + "\\" + Park_Code + "\\" + Park_Code + fc[4:], "NO_TEST", "", "")
            else:
                arcpy.FeatureClassToFeatureClass_conversion(fc, memoryGDB + "\\" + Park_Code, Park_Code + fc[4:])
                arcpy.AlterAliasName(memoryGDB + "\\" + Park_Code + "\\" + Park_Code + fc[4:], describ.aliasName)

#------------Copies Park_Code + "_BEST_BOUNDARY.shp" into a feature class in the compiled geodatabase-----------#
arcpy.FeatureClassToFeatureClass_conversion(Output_Location + "\\" + Park_Code + "_BEST_BOUNDARY.shp", memoryGDB + "\\" + Park_Code, "BEST_BOUNDARY")
arcpy.FeatureToPolygon_management(Output_Location + "\\" + Park_Code + "_BEST_BOUNDARY.shp", Output_Location + "\\" + Park_Code + "_extent_poly.shp")


#------------------Planarize all line feature classes-----------------------#

arcpy.env.workspace = memoryGDB
fds = arcpy.ListDatasets("*", "Feature")
for fd in fds:
    arcpy.env.workspace = fd
    fcs = arcpy.ListFeatureClasses()
    for fc in fcs:
        dsc = arcpy.Describe(fc)
        if dsc.shapeType == "Polyline":
            arcpy.FeatureToLine_management(fc, fc + "_f2l", "", "ATTRIBUTES")
            arcpy.DeleteFeatures_management(fc)
            arcpy.Append_management(fc + "_f2l", fc, "NO_TEST", "", "")
            arcpy.Delete_management(fc + "_f2l")

#-----------------Replaces old boundaries with new boundary & extends/trims boundaries to new boundary----------------#
arcpy.env.workspace = memoryGDB
fds = arcpy.ListDatasets("*", "Feature")
for fd in fds:
    arcpy.env.workspace = fd
    fcs = arcpy.ListFeatureClasses()
    for fc in fcs:
        dsc = arcpy.Describe(fc)
        if dsc.shapeType == "Polygon":
            if arcpy.Exists(fc +"a"): # Delete all boundary features with POS = 10 or 11
                arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_layer", "", "", "")
                arcpy.SelectLayerByAttribute_management(fc +"a_layer", "NEW_SELECTION", '"POS" = 10 OR "POS" = 11')
                arcpy.DeleteFeatures_management(fc + "a_layer")
                arcpy.Delete_management(fc + "a_layer")
                # Copys "BEST_BOUNDARY" into all polygon boundary feature classes then sets the notes
                arcpy.Append_management("BEST_BOUNDARY", fc + "a", "NO_TEST")
                arcpy.MakeFeatureLayer_management(fc + "a", "BEST_BOUNDARY_LYR", '"POS" = 0')
                arcpy.CalculateField_management("BEST_BOUNDARY_LYR", "POS", 10)
                arcpy.Delete_management("BEST_BOUNDARY_LYR")
                arcpy.MakeFeatureLayer_management(fc + "a", "BEST_BOUNDARY_LYR2", '"POS" = 10 OR "POS" = 11')
                arcpy.CalculateField_management("BEST_BOUNDARY_LYR2", "SYM", "\"31.08_10\"", "PYTHON_9.3")
                arcpy.Delete_management("BEST_BOUNDARY_LYR2")
                arcpy.MakeFeatureLayer_management(fc + "a", "BEST_BOUNDARY_LYR3", '"POS" = 10 OR "POS" = 11')
                arcpy.CalculateField_management("BEST_BOUNDARY_LYR3", "NOTES", "\"NA\"", "PYTHON_9.3")
                arcpy.Delete_management("BEST_BOUNDARY_LYR3")
                # Planarizes->Trims->Extends->Planarizes
                arcpy.FeatureToLine_management(fc + "a", fc + "_f2l", "", "ATTRIBUTES")
                arcpy.DeleteFeatures_management(fc + "a")
                arcpy.Append_management(fc + "_f2l", fc + "a", "NO_TEST", "", "")
                arcpy.Delete_management(fc + "_f2l")
                arcpy.TrimLine_edit(fc + "a", Trim_Extend_Length + " Meters", "KEEP_SHORT")
                arcpy.ExtendLine_edit(fc + "a", Trim_Extend_Length + " Meters", "FEATURE")
                arcpy.FeatureToLine_management(fc + "a", fc + "_f2l", "", "ATTRIBUTES")
                arcpy.DeleteFeatures_management(fc + "a")
                arcpy.Append_management(fc + "_f2l", fc + "a", "NO_TEST", "", "")
                arcpy.Delete_management(fc + "_f2l")
            else:
                next

#-----------------Extends/trims all non-boundary line feature classes to new boundary--------------#

for fc in fcs:
    dsc = arcpy.Describe(fc)
    if dsc.shapeType == "Polyline":
        if not fc == "BEST_BOUNDARY":
            if not arcpy.Exists(fc[:-1]):
                # Copys "BEST_BOUNDARY" into all non-boundary feature classes
                arcpy.Append_management("BEST_BOUNDARY", fc, "NO_TEST")
                # Planarizes->Trims->Extends->Planarizes
                arcpy.FeatureToLine_management(fc, fc + "_f2l", "", "ATTRIBUTES")
                arcpy.DeleteFeatures_management(fc)
                arcpy.Append_management(fc + "_f2l", fc, "NO_TEST", "", "")
                arcpy.Delete_management(fc + "_f2l")
                arcpy.ExtendLine_edit(fc, Trim_Extend_Length + " Meters", "FEATURE")
                arcpy.TrimLine_edit(fc, Trim_Extend_Length + " Meters", "KEEP_SHORT")
                arcpy.FeatureToLine_management(fc, fc + "_f2l", "", "ATTRIBUTES")
                arcpy.DeleteFeatures_management(fc)
                arcpy.Append_management(fc + "_f2l", fc, "NO_TEST", "", "")
                arcpy.Delete_management(fc + "_f2l")
                if str(Create_Midpoints) == 'true':
                    if "sec" in fc.lower():
                        next
                    else:
                        Accuracy_Distance = float(Map_Scale) * .000508
                        arcpy.MakeFeatureLayer_management(fc, fc + "mplayer")
                        arcpy.SelectLayerByAttribute_management(fc + "mplayer", "NEW_SELECTION", '"POS" = 0')
                        arcpy.SelectLayerByAttribute_management(fc + "mplayer", "SUBSET_SELECTION", "SHAPE_Length <= " + str(Accuracy_Distance))
                        arcpy.FeatureVerticesToPoints_management(fc + "mplayer", fc + "_edge_match_points", "MID")
                        arcpy.Delete_management(fc + "mplayer")
                        if arcpy.management.GetCount(fc + "_edge_match_points")[0] == "0":
                            arcpy.Delete_management(fc + "_edge_match_points")
                arcpy.MakeFeatureLayer_management(fc, fc + "layer")
                arcpy.SelectLayerByLocation_management(fc + "layer", "SHARE_A_LINE_SEGMENT_WITH", "BEST_BOUNDARY", "", "NEW_SELECTION")
                if int(arcpy.GetCount_management(fc + "layer").getOutput(0)) > 0:
                    arcpy.DeleteFeatures_management(fc + "layer")
                arcpy.Delete_management(fc + "layer")

#----------------------------------Creates new polygons-------------------------#

for fc in fcs:
    dsc = arcpy.Describe(fc)
    if dsc.shapeType == "Polygon":
        if arcpy.Exists(fc + "a"):
            field_names = [f.name for f in arcpy.ListFields(fc)]
            arcpy.Clip_analysis(fc, Output_Location + "\\" + Park_Code + "_extent_poly.shp", fc + "_clip")
            arcpy.FeatureToPoint_management(fc + "_clip", fc + "_labels", "INSIDE")
            arcpy.DeleteFeatures_management(fc)
            arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_lay", "", "", "")
            arcpy.FeatureToPolygon_management(fc + "a_lay", fc + "_new_polys", "", "ATTRIBUTES", fc + "_labels")
            arcpy.Append_management(fc + "_new_polys", fc, "NO_TEST", "", "")
            arcpy.Identity_analysis(fc + "_labels", fc, fc + "_attribute_errors", "ALL", "", "NO_RELATIONSHIPS")
            arcpy.MakeFeatureLayer_management(fc + "_attribute_errors", fc + "_attribute_errors_layer")
            if "SRC_SYM" in field_names:
                arcpy.SelectLayerByAttribute_management(fc + "_attribute_errors_layer", "NEW_SELECTION", "SRC_SYM = SRC_SYM_1")
            else:
                arcpy.SelectLayerByAttribute_management(fc + "_attribute_errors_layer", "NEW_SELECTION", "FTYPE = FTYPE_1")
            if int(arcpy.GetCount_management(fc + "_attribute_errors_layer").getOutput(0)) > 0:
                arcpy.DeleteFeatures_management(fc + "_attribute_errors_layer")

            arcpy.Delete_management(fc + "a_lay")
            arcpy.Delete_management(fc + "_attribute_errors_layer")
            arcpy.Delete_management(fc + "_layer")
            arcpy.Delete_management(fc + "_new_polys")
            arcpy.Delete_management(fc + "_clip")
            arcpy.Delete_management(fc + "_labels")
            arcpy.Delete_management(fc + "_bnd_id")
            arcpy.Delete_management(fc + "_bnd_id_layer")

            if arcpy.management.GetCount(fc + "_attribute_errors")[0] == "0":
                arcpy.Delete_management(fc + "_attribute_errors")

#------------------Populates SYM and NOTES fields for boundary feature classes and creates edge-matching points feature class--------------#
arcpy.Delete_management(Output_Location + "\\" + Park_Code + "_extent_poly.shp")
for fc in fcs:
    dsc = arcpy.Describe(fc)
    if dsc.shapeType == "Polygon":
        field_names = [f.name for f in arcpy.ListFields(fc)]
        if "GLG_SYM" in field_names:
            arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_layer", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "a_layer", "NEW_SELECTION", "POS = 10 OR POS = 11")
            arcpy.Identity_analysis(fc + "a_layer", fc, fc + "_identity", "ALL", "", "KEEP_RELATIONSHIPS")
            arcpy.MakeFeatureLayer_management(fc + "_identity", fc + "_identity_layer", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "_identity_layer", "NEW_SELECTION", "LEFT_SRC_SYM <> '' AND RIGHT_SRC_SYM <> ''")
            arcpy.SelectLayerByLocation_management(fc + "a_layer", "ARE_IDENTICAL_TO", fc + "_identity_layer", "", "NEW_SELECTION", "")
            arcpy.CalculateField_management(fc + "a_layer", "SYM", expression1, "PYTHON", codeblock1)
            arcpy.CalculateField_management(fc + "a_layer", "NOTES", expression2, "PYTHON", codeblock2)
            arcpy.Delete_management(fc + "a_layer")
            arcpy.Delete_management(fc + "_identity_layer")
            arcpy.Delete_management(fc + "_identity")
            if str(Create_Midpoints) == 'true':
                Accuracy_Distance = float(Map_Scale) * .000508
                arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_mplayer")
                arcpy.SelectLayerByAttribute_management(fc + "a_mplayer", "NEW_SELECTION", "SYM = '31.08.01_10'")
                arcpy.SelectLayerByAttribute_management(fc + "a_mplayer", "SUBSET_SELECTION", "SHAPE_Length <= " + str(Accuracy_Distance))
                arcpy.FeatureVerticesToPoints_management(fc + "a_mplayer", fc + "a_edge_match_points", "MID")
                arcpy.Delete_management(fc + "a_mplayer")
                if arcpy.management.GetCount(fc + "a_edge_match_points")[0] == "0":
                        arcpy.Delete_management(fc + "a_edge_match_points")
        else:
            arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_layer", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "a_layer", "NEW_SELECTION", "POS = 10 OR POS = 11")
            arcpy.Identity_analysis(fc + "a_layer", fc, fc + "_identity", "ALL", "", "KEEP_RELATIONSHIPS")
            arcpy.MakeFeatureLayer_management(fc + "_identity", fc + "_identity_layer", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "_identity_layer", "NEW_SELECTION", "LEFT_FTYPE <> 0 AND RIGHT_FTYPE <> 0")
            arcpy.SelectLayerByLocation_management(fc + "a_layer", "ARE_IDENTICAL_TO", fc + "_identity_layer", "", "NEW_SELECTION", "")
            arcpy.CalculateField_management(fc + "a_layer", "SYM", expression1, "PYTHON", codeblock1)
            arcpy.CalculateField_management(fc + "a_layer", "NOTES", expression2, "PYTHON", codeblock2)
            arcpy.Delete_management(fc + "a_layer")
            arcpy.Delete_management(fc + "_identity_layer")
            arcpy.Delete_management(fc + "_identity")
            if str(Create_Midpoints) == 'true':
                Accuracy_Distance = float(Map_Scale) * .000508
                arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_mplayer")
                arcpy.SelectLayerByAttribute_management(fc + "a_mplayer", "NEW_SELECTION", "SYM = '31.08.01_10'")
                arcpy.SelectLayerByAttribute_management(fc + "a_mplayer", "SUBSET_SELECTION", "SHAPE_Length <= " + str(Accuracy_Distance))
                arcpy.FeatureVerticesToPoints_management(fc + "a_mplayer", fc + "a_edge_match_points", "MID")
                arcpy.Delete_management(fc + "a_mplayer")
                if arcpy.management.GetCount(fc + "a_edge_match_points")[0] == "0":
                        arcpy.Delete_management(fc + "a_edge_match_points")
    else:
        next

#--------------------Deletes polygons that don't have attribution and boundaries that don't have real polygons associated with them-----------------#

for fc in fcs:
    dsc = arcpy.Describe(fc)
    if dsc.shapeType == "Polygon":
        field_names = [f.name for f in arcpy.ListFields(fc)]
        if "GLG_SYM" in field_names:
            arcpy.MakeFeatureLayer_management(fc, fc + "_lay", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "_lay", "NEW_SELECTION", "SRC_SYM = ''")
            arcpy.DeleteFeatures_management(fc + "_lay")
            arcpy.Delete_management(fc + "_lay")
            arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_lay")
            arcpy.SelectLayerByAttribute_management(fc + "a_lay", "NEW_SELECTION",  '"POS" = 10 OR "POS" = 11')
            arcpy.Identity_analysis(fc + "a_lay", fc, fc + "_identity2", "ALL", "", "KEEP_RELATIONSHIPS")
            arcpy.MakeFeatureLayer_management(fc + "_identity2", fc + "_identity2_layer", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "_identity2_layer", "NEW_SELECTION", "LEFT_SRC_SYM = '' AND RIGHT_SRC_SYM = ''")
            arcpy.SelectLayerByLocation_management(fc + "a_lay", "ARE_IDENTICAL_TO", fc + "_identity2_layer", "", "NEW_SELECTION", "")
            arcpy.DeleteFeatures_management(fc + "a_lay")
            arcpy.Delete_management(fc + "a_lay")
            arcpy.Delete_management(fc + "_identity2")
            arcpy.Delete_management(fc + "_identity2_layer")
        else:
            arcpy.MakeFeatureLayer_management(fc, fc + "_lay", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "_lay", "NEW_SELECTION", "FTYPE = 0")
            arcpy.DeleteFeatures_management(fc + "_lay")
            arcpy.Delete_management(fc + "_lay")
            arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_lay")
            arcpy.SelectLayerByAttribute_management(fc + "a_lay", "NEW_SELECTION",  '"POS" = 10 OR "POS" = 11')
            arcpy.Identity_analysis(fc + "a_lay", fc, fc + "_identity2", "ALL", "", "KEEP_RELATIONSHIPS")
            arcpy.MakeFeatureLayer_management(fc + "_identity2", fc + "_identity2_layer", "", "", "")
            arcpy.SelectLayerByAttribute_management(fc + "_identity2_layer", "NEW_SELECTION", "LEFT_FTYPE = 0 AND RIGHT_FTYPE = 0")
            arcpy.SelectLayerByLocation_management(fc + "a_lay", "ARE_IDENTICAL_TO", fc + "_identity2_layer", "", "NEW_SELECTION", "")
            arcpy.DeleteFeatures_management(fc + "a_lay")
            arcpy.Delete_management(fc + "a_lay")
            arcpy.Delete_management(fc + "_identity2")
            arcpy.Delete_management(fc + "_identity2_layer")

#---------------------------Caculates GMAP ID of boundary feature classes from Polygons to the upper left---------------#

for fc in fcs:
    if arcpy.Exists(fc + "a"):
        arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_lay")
        arcpy.SelectLayerByAttribute_management(fc + "a_lay", "NEW_SELECTION",  '"POS" = 10 OR "POS" = 11')
        #any non-glga boundary fc with pos of 10,11 neeeds the subtype set to 1
        if fc[-3:] <> "glg":
             arcpy.CalculateField_management(fc + "a_lay", "FSUBTYPE", 2)

        arcpy.Identity_analysis(fc + "a_lay", fc, fc + "_identity2", "ALL", "", "KEEP_RELATIONSHIPS")
        arcpy.MakeFeatureLayer_management(fc + "_identity2", fc + "_identity2_layer", "", "", "")
        arcpy.SpatialJoin_analysis(fc + "a_lay", fc + "_identity2_layer", fc + "a_join", "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "SHARE_A_LINE_SEGMENT_WITH", "", "")
        arcpy.CalculateField_management(fc + "a_join", "GMAP_ID", expression3, "PYTHON", codeblock3)
        arcpy.DeleteFeatures_management(fc + "a_lay")
        arcpy.Delete_management(fc + "a_lay")
        arcpy.Delete_management(fc + "_identity2_layer")
        arcpy.Append_management(fc + "a_join", fc + "a", "NO_TEST", "", "")
        arcpy.Delete_management(fc + "a_join")
        arcpy.Delete_management(fc + "_identity2")

#-------------------------Deletes temporary boundary shapefile-------------------------#

for fc in fcs:
    if fc == "BEST_BOUNDARY":
        arcpy.Delete_management(fc)

#--------------------Fixes small contacts on boundaries that inherit attributes from the wrong source map------------------------#
#----------------------LOOK HERE IF SOMETHING GOES WRONG------#    DELETE THIS PART OF THE CODE? Covers up errors of pre-edgematched datasets!

for fc in fcs:
    if arcpy.Exists(fc + "a"):
        arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_layer")
        arcpy.MakeFeatureLayer_management(fc, fc + "_layer")
        arcpy.SelectLayerByAttribute_management(fc + "a_layer", "NEW_SELECTION", '"POS" <> 10 AND "POS" <> 11')
        arcpy.FeatureToLine_management([fc +"a_layer", fc + "_layer"], fc + "_feature_to_line", "", "ATTRIBUTES")
        arcpy.Dissolve_management(fc + "_feature_to_line", fc + "_dissolve", ["POS", "FSUBTYPE", "NOTES", "GMAP_ID_1"], "", "SINGLE_PART", "DISSOLVE_LINES")
        arcpy.AlterField_management(fc + "_dissolve", "GMAP_ID_1", "GMAP_ID")
        arcpy.DeleteFeatures_management(fc + "a_layer")
        arcpy.MakeFeatureLayer_management(fc + "_dissolve", fc + "_dissolve_lyr")
        arcpy.SelectLayerByAttribute_management(fc + "_dissolve_lyr", "NEW_SELECTION", '"POS" = 0')
        arcpy.DeleteFeatures_management(fc + "_dissolve_lyr")
        arcpy.Append_management(fc + "_dissolve_lyr", fc + "a_layer", "NO_TEST")
        arcpy.Delete_management(fc + "_feature_to_line")
        arcpy.Delete_management(fc + "_dissolve")
        arcpy.Delete_management(fc + "a_layer")
        arcpy.Delete_management(fc + "_layer")

#--------------------"Planarize" boundary fcs and dissolve polys---------------------------------------------#

for fc in fcs:
    if arcpy.Exists(fc + "a"):
        arcpy.MakeFeatureLayer_management(fc + "a", fc + "a_layer")
        arcpy.FeatureToLine_management([fc + "a_layer"],fc + "_f2l_lyr","", "ATTRIBUTES")
        arcpy.DeleteFeatures_management(fc + "a_layer")
        arcpy.Append_management(fc + "_f2l_lyr", fc + "a_layer", "NO_TEST")
        arcpy.Delete_management(fc + "_f2l_lyr")
        arcpy.Delete_management(fc + "a_layer")
        arcpy.MakeFeatureLayer_management(fc, fc + "_lyr")
        field_names = [f.name for f in arcpy.ListFields(fc)]
        if "GLG_SYM" in field_names:
            dissolveFields = ["SRC_SYM", "NOTES", "GMAP_ID", ]
        else:
            dissolveFields = ["FTYPE", "NOTES", "GMAP_ID"]
        arcpy.Dissolve_management(fc + "_lyr", fc + "_lyr_dissolve", dissolveFields, "", "SINGLE_PART")
        arcpy.DeleteFeatures_management(fc + "_lyr")
        arcpy.Append_management(fc + "_lyr_dissolve", fc, "NO_TEST")
        arcpy.Delete_management(fc + "_lyr")
        arcpy.Delete_management(fc + "_lyr_dissolve")

#-------------------------------Deletes Existing Topology-----------------------------#

arcpy.env.workspace = memoryGDB
fds = arcpy.ListDatasets("*", "Feature")
for fd in fds:
    arcpy.env.workspace = fd
    tops = arcpy.ListDatasets("*", "All")
    for top in tops:
        if top.endswith("_topology"):
            arcpy.Delete_management(top)

arcpy.management.Copy(memoryGDB, Compile_Geodatabase)


if str(Create_Topology) == 'true':
    arcpy.env.workspace = Output_Location + "\\" + Park_Code + "_" + mapType + ".gdb"
    GP = arcgisscripting.create()
    try:
        from topology import * # topology92.py file must be in the same directory as this script
    except:
        arcpy.AddMessage("Unable to add topology")

    AddTopology(GP, Output_Location + "\\" + Park_Code + "_" + mapType + ".gdb")
else:
    arcpy.AddMessage("Topology was not created")



