#from pyramid.response import Response
from pyramid.view import view_config
from .models import (
    User,
    Achievement,
    Value
    )

from urlcache import get_or_set
from pyramid.renderers import render, JSON

from .flaskadmin import flaskadminapp
from pyramid.wsgi import wsgiapp2, wsgiapp
from _collections import defaultdict
from gengine.models import Variable, valid_timezone, Goal, AchievementReward
from werkzeug.exceptions import BadRequest
from gengine.urlcache import set_value
from pyramid.exceptions import NotFound
from werkzeug import DebuggedApplication
from gengine.wsgiutil import HTTPSProxied

@view_config(route_name='add_or_update_user', renderer='string')
def add_or_update_user(request):
    """add a user and set its metadata"""
    
    user_id = long(request.matchdict["user_id"])
    
    lat = float(request.POST["lat"])
    lon = float(request.POST["lon"])
    friends = [long(x) for x in request.POST["friends"].split(",")]
    timezone = request.POST["timezone"]
    
    if not valid_timezone(timezone):
        timezone = 'UTC'
    
    country = request.POST["country"]
    region = request.POST["region"]
    city = request.POST["city"]
    
    User.set_infos(user_id=user_id,
                   lat=lat,
                   lng=lon,
                   timezone=timezone,
                   country=country,
                   region=region,
                   city=city,
                   friends=friends)
    
    return {"status" : "OK"}

@view_config(route_name='delete_user', renderer='string', request_method="DELETE")
def delete_user(request):
    """delete a user completely"""
    
    user_id = long(request.matchdict["user_id"])
    User.delete_user(user_id)
    return {"status" : "OK"}

@view_config(route_name='get_progress', renderer='string')
def get_progress(request, return_object=False):
    """get all relevant data concerning the user's progress"""
    user_id = long(request.matchdict["user_id"])
    
    user = User.get_user(user_id)
    if not user:
        raise NotFound("user not found")
    
        
    def generate():
        achievements = Achievement.get_achievements_by_user_for_today(user)
        
        def ea(achievement):
            try:
                return Achievement.evaluate(user, achievement["id"])
            except:
                return None
            
        check = lambda x : x!=None and (x["hidden"]==False or x["level"]>0)
        
        ret = {
            "achievements" : {
              x["id"] : x for x in [ea(achievement) for achievement in achievements] if check(x) 
            }
        }
        
        if return_object:
            return render("json",ret),ret
        else:
            return render("json",ret)
    
    key = "/progress/"+str(user_id)
    
    if not return_object:
        request.response.content_type = 'application/json'
        return get_or_set(key,generate)
    else:
        ret_str, ret = generate()
        set_value(key,ret_str)
        return ret
    
@view_config(route_name='increase_value', renderer='json', request_method="POST")
@view_config(route_name='increase_value_with_key', renderer='json', request_method="POST")
def increase_value(request):
    """increase a value for the user"""
    
    user_id = int(request.matchdict["user_id"])
    try:
        value = float(request.POST["value"])
    except:
        raise BadRequest("Invalid value provided")
    
    key = request.matchdict["key"] if request.matchdict.has_key("key") else ""
    variable_name = request.matchdict["variable_name"]
    
    user = User.get_user(user_id)
    if not user:
        raise NotFound("user not found")
    
    variable = Variable.get_variable_by_name(variable_name)
    if not variable:
        raise NotFound("variable not found")
    
    Value.increase_value(variable_name, user, value, key) 
    
    output = get_progress(request,return_object=True)
    
    for aid in output["achievements"].keys():
        if len(output["achievements"][aid]["new_levels"])>0:
            del output["achievements"][aid]["levels"]
            del output["achievements"][aid]["priority"]
            del output["achievements"][aid]["goals"]
        else:
            del output["achievements"][aid]
    return output

@view_config(route_name='get_achievement_level', renderer='string', request_method="GET")
def get_achievement_level(request):
    """get all information about an achievement for a specific level""" 
    try:
        achievement_id = int(request.matchdict.get("achievement_id",None))
        level = int(request.matchdict.get("level",None))
    except:
        raise BadRequest("invalid input")
         
    def generate():
        achievement = Achievement.get_achievement(achievement_id)
         
        if not achievement:
            raise NotFound("achievement not found")
         
        level_output = Achievement.basic_output(achievement, [], True, level).get("levels").get(str(level), {"properties":{},"rewards":{}})
        if level_output.has_key("goals"):
            del level_output["goals"]
        if level_output.has_key("level"):
            del level_output["level"]
        return render("json",level_output)
     
    key = "/achievement/"+str(achievement_id)+"/level/"+str(level)
    request.response.content_type = 'application/json'
         
    return get_or_set(key,generate)
    
@view_config(route_name='admin')
@wsgiapp2
def admin(environ, start_response):
    return HTTPSProxied(DebuggedApplication(flaskadminapp.wsgi_app, True))(environ,start_response)
    #return 