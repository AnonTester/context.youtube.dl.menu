# service.py - starting point of the service
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import sys, os, traceback, subprocess
#from lib.yd_private_libs import util, servicecontrol, updater
import xbmc
import xbmcgui
import xbmcaddon
import re
import io
from xml.etree import ElementTree as ET
import shutil

this_addon = xbmcaddon.Addon()
addon_path = xbmc.translatePath(this_addon.getAddonInfo("path"))
addonID = this_addon.getAddonInfo("id")
addonFolder = this_addon.getAddonInfo("path")
IDLE_TIME = 1 # 1 second

def add_context_youtube_dl_menu_button():
    """
    Add context_youtube_dl_menu button to Video OSD Window of current skin
    :return: True - if button was added successfully, False - otherwise
    :rtype: bool
    """

    global NEED_RESTART
    current_skin_id = xbmc.getSkinDir()
    skin_folder_home = xbmc.translatePath("special://home/addons/" + current_skin_id)
    if not os.path.exists(skin_folder_home):
        #skin_folder_system = xbmc.translatePath("special://xbmc/addons/" + current_skin)
        current_skin = xbmcaddon.Addon(current_skin_id)
        skin_folder_system = xbmc.translatePath(current_skin.getAddonInfo("path"))
        if not os.path.exists(skin_folder_system):
            error("Couldn't find folder of skin " + current_skin_id)
            return False
        else:
            try:
                shutil.copytree(skin_folder_system, skin_folder_home)
            except Exception as e:
                log_exception(str(e))
                message = "Couldn't copy skin from {0} to {1}".format(skin_folder_system,
                                                                      skin_folder_home)
                error(message)
                return False
            NEED_RESTART = True
    if not copy_icons(skin_folder_home):
        return False
    res_folder = get_default_resolution_folder(skin_folder_home)
    if not res_folder:
        error("Couldn't get default resolution folder for skin " + current_skin_id)
        return False

    #patching VideoOSD.xml
    videoosdxml_path = os.path.join(skin_folder_home, res_folder, "VideoOSD.xml")
    try:
        with io.open(videoosdxml_path, "r", encoding="utf-8") as videoosdxml:
            old_text = videoosdxml.read()
    except Exception as e:
        log_exception("Couldn't get text of VideoOSD.xml")
        log_exception(str(e))
        return
    if old_text.find(YTDL_MENU_BUTTON_START_TEXT) >= 0:
        NEED_RESTART = False
        return True
    context_youtube_dl_menu_button_text = get_context_youtube_dl_menu_button_text()
    new_text = old_text.replace("<control type=\"radiobutton\" id=\"70043\">", context_youtube_dl_menu_button_text + "<control type=\"radiobutton\" id=\"70043\">")
    try:
        with io.open(videoosdxml_path, "w", encoding="utf-8") as videoosdxml:
            videoosdxml.write(new_text)
    except Exception as e:
        error("Couldn't write to skin folder")
        log_exception(str(e))
        return False

    #patching Variables.xml
    variablesxml_path = os.path.join(skin_folder_home, res_folder, "Variables.xml")
    try:
        with io.open(variablesxml_path, "r", encoding="utf-8") as variablesxml:
            old_help_text = variablesxml.read()
    except Exception as e:
        log_exception("Couldn't get text of Variables.xml")
        log_exception(str(e))
        return
    if old_help_text.find(YTDL_MENU_BUTTON_START_TEXT) >= 0:
        NEED_RESTART = False
        return True
    context_youtube_dl_menu_button_help_text = get_context_youtube_dl_menu_button_help_text()
    new_text = old_help_text.replace("<value condition=\"Control.HasFocus(70043)\">", context_youtube_dl_menu_button_help_text + "<value condition=\"Control.HasFocus(70043)\">")
    try:
        with io.open(variablesxml_path, "w", encoding="utf-8") as variablesxml:
            variablesxml.write(new_text)
    except Exception as e:
        error("Couldn't write to skin folder")
        log_exception(str(e))
        return False


    if not NEED_RESTART:
        xbmc.executebuiltin("ReloadSkin()")
    return True


def delete_context_youtube_dl_menu_icon():
    """
    Delete Recording icon from current skin
    :return: None
    """

    current_skin_id = xbmc.getSkinDir()
    skin_folder = xbmc.translatePath("special://home/addons/" + current_skin_id)
    res_folder = get_default_resolution_folder(skin_folder)
    if not res_folder:
        log_exception("Couldn't get default resolution folder for skin " + current_skin_id)
        return
    videoosdxml_path = os.path.join(skin_folder, res_folder, "VideoOSD.xml")
    with io.open(videoosdxml_path, "r", encoding="utf-8") as videoosdxml:
        old_text = videoosdxml.read()
    start_pos = old_text.find(YTDL_MENU_BUTTON_START_TEXT)
    if start_pos == -1:
        log_exception("Couldn't find context_youtube_dl_menu button")
        return
    end_pos = old_text.find(YTDL_MENU_BUTTON_END_TEXT)
    if end_pos == -1:
        log_exception("Couldn't find end of context_youtube_dl_menu button")
        return
    len_end_text = len(YTDL_MENU_BUTTON_END_TEXT)
    new_text = old_text[:start_pos] + old_text[end_pos + len_end_text:]
    try:
        with io.open(videoosdxml_path, "w", encoding="utf-8") as videoosdxml:
            videoosdxml.write(new_text)
    except Exception as e:
        log_exception("Couldn't write to skin VideoOSD.xml")
        log_exception(str(e))

    #removing help variable
    variablesxml_path = os.path.join(skin_folder, res_folder, "Variables.xml")
    with io.open(variablesxml_path, "r", encoding="utf-8") as variablesxml:
        old_text = variablesxml.read()
    start_pos = old_text.find(YTDL_MENU_BUTTON_START_TEXT)
    if start_pos == -1:
        log_exception("Couldn't find context_youtube_dl_menu help variable")
        return
    end_pos = old_text.find(YTDL_MENU_BUTTON_END_TEXT)
    if end_pos == -1:
        log_exception("Couldn't find end of context_youtube_dl_menu help variable")
        return
    len_end_text = len(YTDL_MENU_BUTTON_END_TEXT)
    new_text = old_text[:start_pos] + old_text[end_pos + len_end_text:]
    try:
        with io.open(variablesxml_path, "w", encoding="utf-8") as variablesxml:
            variablesxml.write(new_text)
    except Exception as e:
        log_exception("Couldn't write to skin Variables.xml")
        log_exception(str(e))

def image(filename):
    """
    Construct full filename of the image, using short name
    and path to addon folder
    :param filename: short filename of the image
    :return: full filename of the image
    :rtype: str
    """

    addon_folder = xbmc.translatePath(this_addon.getAddonInfo("path"))
    return os.path.join(addon_folder,
                        "resources",
                        "img",
                        filename)


def copy_icons(skin_folder):
    """
    Copy icons from context.youtube.dl.menu folder to the folder of current skin
    :param skin_folder: path to current skin folder
    :type skin_folder: str
    :return: True - if icons were successfully copied, False - otherwise
    :rtype: bool
    """

    for icon in ["youtube_red.png", "youtube_gray.png"]:
        try:
            src = image(icon)
            dst = os.path.join(skin_folder, "media", icon)
            shutil.copyfile(src, dst)
        except Exception as e:
            log_exception(str(e))
            message = "Couldn't copy icon from {0} to {1}".format(src, dst)
            error(message)
            return False
    return True


def get_default_resolution_folder(skin_folder):
    """
    Get default resolution folder for current skin
    :return: short name of the folder, example "720p"
    :rtype: str
    """

    addonxmlname = os.path.join(skin_folder, "addon.xml")
    try:
        tree = ET.parse(addonxmlname)
    except Exception as e:
        log_exception("Couldn't parse " + addonxmlname)
        log_exception(str(e))
        return None
    root = tree.getroot()
    aspect_ratio = xbmc.getInfoLabel("Skin.AspectRatio()")
    default = None
    for child in root:
        if child.tag == "extension":
            if child.attrib.get("point", "") == "xbmc.gui.skin":
                for child2 in child:
                    if child2.tag == "res":
                        if child2.attrib.get("aspect","") == aspect_ratio:
                            return child2.attrib.get("folder", None)
                        if child2.attrib.get("default", "") == "true":
                            default = child2.attrib.get("folder", None)
    return default


def get_context_youtube_dl_menu_button_text():
    path = os.path.join(addon_path, "YoutubeButton.txt")
    text = ""
    with io.open(path, "r", encoding="utf-8") as context_youtube_dl_menu_button_template:
        text = context_youtube_dl_menu_button_template.read()
    return text

def get_context_youtube_dl_menu_button_help_text():
    path = os.path.join(addon_path, "YoutubeButton_Help.txt")
    text = ""
    with io.open(path, "r", encoding="utf-8") as context_youtube_dl_menu_button_help_template:
        text = context_youtube_dl_menu_button_help_template.read()
    return text


def start_service():
    """
    Start service
    :return: None
    """

    enable_service = this_addon.getSetting("enable_service")
    if enable_service != "true":
        return

    result = add_context_youtube_dl_menu_button()

    if result and NEED_RESTART:
        question = xbmcgui.Dialog()
        if question.yesno("Need restart",
                       "To enable the youtube dl button in the Video OSD, you need to restart Kodi. Exit now?"):
            xbmc.executebuiltin("Quit()")

    monitor = xbmc.Monitor()

    while not monitor.abortRequested():
        if monitor.waitForAbort(IDLE_TIME):
            # Abort was requested while waiting. We should exit
            break

    delete_context_youtube_dl_menu_icon()


def set_setting_value(name, value):
    """
    Set Kodi settings value
    :param name: of the setting. Example: "services.webserver"
    :type name: str
    :param value: value of the setting. Example: True
    :return: True - if setting was changed successfully; False - otherwise.
    :rtype: bool
    """

    str_value = json.dumps(value)
    command = '{"jsonrpc":"2.0", "id":1, ' \
              '"method":"Settings.SetSettingValue",' \
              '"params":{"setting":"' + name + '",' \
              '"value":' + str_value + '}}'
    try:
        xbmc.executeJSONRPC(command)
    except Exception as e:
        log_exception("Couldn't change setting")
        debug(command)
        log_exception(str(e))
        return False
    return True

def get_setting(name):
    """
    Get Kodi setting
    :param name: id of the setting.
        Example:
    :type name: str
    :return: string value of the setting
    :rtype: str
    """

    command = '{"jsonrpc":"2.0", "id":1, ' \
              '"method":"Settings.GetSettingValue",' \
              '"params":{"setting":"' + name + '"}}'
    try:
        response = xbmc.executeJSONRPC(command)
    except Exception as e:
        log_exception("Couldn't execute JSON-RPC")
        debug(command)
        log_exception(str(e))
        return
    try:
        data = json.loads(response)
    except Exception as e:
        log_exception("Couldn't parse JSON response")
        debug(response)
        log_exception(str(e))
        return None

    debug("data: " + str(data))
    result = data.get("result")
    if result:
        return result.get("value")
    else:
        return None

def debug(content):
    """
    Outputs content to log file
    :param content: content which should be output
    :return: None
    """
    if type(content) is str:
        message = unicode(content, "utf-8")
    else:
        message = content
    log(message, xbmc.LOGDEBUG)

def error(message):
    """
    Opens notification window with error message
    :param: message: str - error message
    :return: None
    """
    notify("Error:," + message)

def info(message):
    """
    Opens info windows with message
    :param: message: str - message
    :return: None
    """

    notify("Info:," + message)


def notify(message):
    """
    Opens notification window with message
    :param: message: str - message
    :return: None
    """
    icon = os.path.join(addonFolder, "icon.png")
    xbmc.executebuiltin(unicode('XBMC.Notification(' + message + ',3000,' + icon + ')').encode("utf-8"))

def log_exception(content):
    """
    Outputs content to log file
    :param content: content which should be output
    :return: None
    """

    if type(content) is str:
        message = unicode(content, "utf-8")
    else:
        message = content
    log(message, xbmc.LOGERROR)


def log(msg, level=xbmc.LOGNOTICE):
    """
    Outputs message to log file
    :param msg: message to output
    :param level: debug levelxbmc. Values:
    xbmc.LOGDEBUG = 0
    xbmc.LOGERROR = 4
    xbmc.LOGFATAL = 6
    xbmc.LOGINFO = 1
    xbmc.LOGNONE = 7
    xbmc.LOGNOTICE = 2
    xbmc.LOGSEVERE = 5
    xbmc.LOGWARNING = 3
    """

    log_message = u'{0}: {1}'.format(addonID, msg)
    xbmc.log(log_message.encode("utf-8"), level)


YTDL_MENU_BUTTON_START_TEXT = "<!-- context.youtube.dl.menu_start -->"
YTDL_MENU_BUTTON_END_TEXT = "<!-- context.youtube.dl.menu_end -->"
NEED_RESTART = False

start_service()

