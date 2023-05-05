import sys
from nidm.core import Constants
from nidm.experiment import Navigate
import nidm.experiment.tools.rest


def GetProjectsComputedMetadata(nidm_file_list):
    """
     :param nidm_file_list: List of one or more NIDM files to query across for list of Projects
    :return: Dictionary or projects, each project having a dictionary of project stats
             including age_max, age_min, gender list, and handedness list.
    """

    meta_data = {"projects": {}}
    projects = Navigate.getProjects(tuple(nidm_file_list))
    for p in projects:
        proj_id = nidm.experiment.tools.rest.RestParser.getTailOfURI(str(p))
        meta_data["projects"][proj_id] = {
            "age_max": 0,
            "age_min": sys.maxsize,
            "gender": [],
            "handedness": [],
        }
        meta_data["projects"][proj_id].update(
            Navigate.GetProjectAttributes(tuple(nidm_file_list), p)
        )
        gender_set = set()
        hand_set = set()
        subjects = Navigate.getSubjects(tuple(nidm_file_list), p)
        for s in subjects:
            activities = Navigate.getActivities(tuple(nidm_file_list), s)
            meta_data["projects"][proj_id]["number_of_subjects"] = len(subjects)

            for a in activities:
                data = Navigate.getActivityData(tuple(nidm_file_list), a)
                if type(data) == Navigate.ActivityData:
                    for x in data.data:
                        if x.isAbout == Constants.NIDM_IS_ABOUT_AGE:
                            if (
                                float(x.value)
                                > meta_data["projects"][proj_id]["age_max"]
                            ):
                                meta_data["projects"][proj_id]["age_max"] = float(
                                    x.value
                                )
                            if (
                                float(x.value)
                                < meta_data["projects"][proj_id]["age_min"]
                            ):
                                meta_data["projects"][proj_id]["age_min"] = float(
                                    x.value
                                )
                        if x.isAbout == Constants.NIDM_IS_ABOUT_GENDER:
                            gender_set.add(str(x.value))
                        if x.isAbout == Constants.NIDM_IS_ABOUT_HANDEDNESS:
                            hand_set.add(str(x.value))
        meta_data["projects"][proj_id]["gender"] = list(gender_set)
        meta_data["projects"][proj_id]["handedness"] = list(hand_set)

    return meta_data
    # meta_data = GetProjectsMetadata(nidm_file_list)
    # ExtractProjectSummary(meta_data, nidm_file_list)

    # return compressForJSONResponse(meta_data)
