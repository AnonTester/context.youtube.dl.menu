# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import sys, os, traceback, subprocess
#from lib.yd_private_libs import util, servicecontrol, updater
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import re
if sys.version_info.major == 3:
    import urllib.parse as urllib
    from functools import reduce
else:
    import urllib
import datetime, time

ADDON = xbmcaddon.Addon(id='script.module.youtube.dl')
DEBUG = ADDON.getSetting('debug') == 'true'

#fixes required for youtube-dl module addon
sys.path.append('../script.module.youtube.dl/lib/')

###############################################################################
# FIX: xbmcout instance in sys.stderr does not have isatty(), so we add it
###############################################################################
class replacement_stderr(sys.stderr.__class__):
    def isatty(self):
        return False

sys.stderr.__class__ = replacement_stderr
###############################################################################

###############################################################################
# FIXES: datetime.datetime.strptime evaluating as None in Kodi
###############################################################################
try:
    datetime.datetime.strptime('0', '%H')
except TypeError:
    # Fix for datetime issues with XBMC/Kodi
    class new_datetime(datetime.datetime):
        @classmethod
        def strptime(cls, dstring, dformat):
            return datetime.datetime(*(time.strptime(dstring, dformat)[0:6]))

    datetime.datetime = new_datetime
###############################################################################

###############################################################################
# FIX: _subprocess doesn't exist on Xbox One
###############################################################################
try:
    import _subprocess
except ImportError:
    from yd_private_libs import _subprocess
###############################################################################

try:
    import youtube_dl
except:
    util.ERROR('Failed to import youtube-dl')
    youtube_dl = None

perc = 0
addon = xbmcaddon.Addon()
addonID = addon.getAddonInfo('id')
if sys.version_info.major == 3:
    addonFolder = xbmc.translatePath('special://home/addons/'+addonID)
else:
    addonFolder = xbmc.translatePath('special://home/addons/'+addonID).decode('utf-8')
finalformat = ""

def getDownloadPath(use_default=None):
    if use_default is None:
        use_default = not ADDON.getSetting('confirm_download_path') == True
    path = ADDON.getSetting('last_download_path')
    if path:
        if not use_default:
            new = xbmcgui.Dialog().yesno("Use Default?", "Use default path:", path, "Or choose a new path?", "Default", "New")
            if new:
                path = ''
    if not path:
        path = xbmcgui.Dialog().browse(3, "Select Directory", 'files', '', False, True)
    if not path:
        return
    ADDON.setSetting('last_download_path', path)
    return path

class MyLogger(object):
    def debug(self, msg):
        global perc
        global pDialog
        perc += 20
        LOG("dbg "+msg, debug=True)
        pDialog.update(perc, msg)

    def warning(self, msg):
        global perc
        global pDialog
        global finalformat
        perc += 20
        LOG("wrn "+msg, debug=True)
        pDialog.update(perc, msg)
        if 'merged into mkv' in msg:
            finalformat='mkv'
        elif 'merged into webm' in msg:
            finalformat='webm'
        elif 'merged into mp4' in msg:
            finalformat='mp4'
        elif 'Merging formats into' in msg and '.webm' in msg:
            finalformat='webm'
        elif 'Merging formats into' in msg and '.mkv' in msg:
            finalformat='mkv'
        elif 'Merging formats into' in msg and '.mp4' in msg:
            finalformat='mp4'
        else:
            finalformat=''

    def error(self, msg):
        global perc
        global pDialog
        perc += 20
        LOG("err "+msg, debug=True)
        pDialog.update(perc, msg)

def my_hook(d):
    global pDialog
    if d['status'] == 'downloading':
        pDialog.update(int(float(d['_percent_str'][:-1])), d['_eta_str'])
        
def my_hook_empty(d):
    return

def LOG(msg,debug=False):
    if debug and not DEBUG: return
    xbmc.log('context.youtube.dl.menu: {0}'.format(msg), xbmc.LOGNOTICE)

def ERROR(msg=None,hide_tb=False):
    if msg: LOG('ERROR: {0}'.format(msg))
    if hide_tb and not DEBUG:
        errtext = sys.exc_info()[1]
        LOG('%s::%s (%d) - %s' % (msg or '?', sys.exc_info()[2].tb_frame.f_code.co_name, sys.exc_info()[2].tb_lineno, errtext))
        return
    xbmc.log(traceback.format_exc(), xbmc.LOGNOTICE)

class main():
    def __init__(self):
        self.download(None)

    def playlist():
        YOUTUBE_VIDEO_URL = 'http://www.youtube.com/playlist?list=%s'
        playlist_id = False

        container_url=xbmc.getInfoLabel('container.folderpath')
        #urldecoding url 5 times to account for nested addon-calls
        container_url=urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(container_url)))))
        xbmc.log('context.youtube.dl.menu: '+'Container.FolderPath: |%s|' % container_url, xbmc.LOGNOTICE)

        plugin_url = sys.listitem.getPath()
        #urldecoding url 5 times to account for nested addon-calls
        plugin_url = urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(plugin_url)))))
        xbmc.log('context.youtube.dl.menu: '+'ListItem.FileNameAndPath: |%s|' % plugin_url, xbmc.LOGNOTICE)

        if plugin_url:
            result = re.search('playlist/(?P<playlist_id>[a-zA-Z0-9_-]+)', plugin_url)
            if result:
                xbmc.log('context.youtube.dl.menu: '+'Found playlist_id in url: |%s|' % result.group('playlist_id'), xbmc.LOGNOTICE)
                playlist_id=result.group('playlist_id')
            else:
                xbmc.log('context.youtube.dl.menu: '+'playlist_id not found in url '+plugin_url, xbmc.LOGERROR)
        else:
            xbmc.log('context.youtube.dl.menu: '+'Plugin URL not found', xbmc.LOGERROR)

        #Fallback to container
        if container_url and not playlist_id:
            result = re.search('playlist/(?P<playlist_id>[a-zA-Z0-9_-]+)', container_url)
            if result:
                xbmc.log('context.youtube.dl.menu: '+'Found playlist_id in container url: |%s|' % result.group('playlist_id'), xbmc.LOGNOTICE)
                playlist_id=result.group('playlist_id')
            else:
                xbmc.log('context.youtube.dl.menu: '+'playlist_id not found in container url '+plugin_url, xbmc.LOGERROR)
        else:
            xbmc.log('context.youtube.dl.menu: '+'Container URL not found', xbmc.LOGERROR)

        
        if not playlist_id:
            xbmcgui.Dialog().notification('youtube-dl error','playlist id not found',os.path.join(addonFolder, "icon.png"),5000,True)
            return 1

        playlisturl=YOUTUBE_VIDEO_URL % playlist_id

        ydl_opts = {
            'ignoreerrors' : True,
            'extract_flat': True,
            #'logger': MyLogger(),
            'progress_hooks': [my_hook_empty],
            }

        xbmc.log('context.youtube.dl.menu: '+repr(ydl_opts), xbmc.LOGERROR)

        if xbmc.Player().isPlaying():
            xbmcgui.Dialog().notification('youtube-dl','Playlist download started',os.path.join(addonFolder, "icon.png"),5000,True)

        playlistDLProgress = xbmcgui.DialogProgressBG()
        playlistDLProgress.create('YoutubeDL', 'Preparing to download playlist ...')

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(playlisturl,download=False)
            except:
                playlistDLProgress.close()
                xbmc.log('context.youtube.dl.menu: '+'Fatal error '+sys.exc_info()[0], xbmc.LOGERROR)
                ERROR("Fatal YTD Error")
                xbmcgui.Dialog().notification('youtube-dl error','Fatal YTD Error, check logs',os.path.join(addonFolder, "icon.png"),5000,True)
                return False

            if ydl_info == None:
                playlistDLProgress.close()
                xbmc.log('context.youtube.dl.menu: '+'Fatal error, youtube-dl core may need to be updated.', xbmc.LOGERROR)
                xbmcgui.Dialog().notification('youtube-dl error','Could not obtain playlist, check logs',os.path.join(addonFolder, "icon.png"),5000,True)
                return False

            #ydl_formats = ydl.list_formats(ydl_info)
            #LOG("YTD Formats: "+repr(ydl_formats), debug=True)
            LOG(repr(ydl_info), debug=True)

            LOG(repr(ydl_info['entries']), debug=True)
            amt = len(ydl_info['entries']);
            LOG("Entries: "+str(amt), debug=True)

            if amt > 10:
                amtwarning = "Playlist contains "+str(amt)+' videos.\nThis may take a while!\nDownload them all ?'
            else:
                amtwarning = "Playlist contains "+str(amt)+' videos.\nDownload them all ?'

            continuedownload = xbmcgui.Dialog().yesno('Continue downloading?', amtwarning, '')
            if not continuedownload:
                LOG("Abort playlist download.", debug=True)
                playlistDLProgress.close()
                xbmcgui.Dialog().notification('youtube-dl','Playlist download aborted',os.path.join(addonFolder, "icon.png"),5000,True)
                return False
            else:
                playlistDLProgress.update(0, 'Downloading Playlist...', 'Downloading playlist ...')
                LOG("Downloading playlist.", debug=True)
                YOUTUBE_VIDEO_URL = 'http://www.youtube.com/v/%s'
                i=0
                for entry in ydl_info['entries']:
                    i+=1
                    url=YOUTUBE_VIDEO_URL % entry['url']
                    LOG("Downloading url "+url, debug=True)
                    info = {'url': url, 'title': entry['title'], 'id': entry['url'], 'media_type': 'video'}
                    LOG("percentage"+str(int(100/amt*i)), debug=True)
                    
                    if sys.version_info.major == 3:
                        playlistDLProgress.update(int(100/amt*i), 'Downloading Playlist...', 'Downloading '+entry['title']+' ...')
                    else:
                        playlistDLProgress.update(int(100/amt*i), 'Downloading Playlist...', 'Downloading '+entry['title'].decode('latin1')+' ...')
                    try:
                        main.download(info,True)
                    except:
                        LOG("Problem downloading "+url+". Skipping it...", debug=True)
                        continue
                LOG("Finished playlist download.", debug=True)
                xbmc.sleep(1000)
                playlistDLProgress.close()
                xbmcgui.Dialog().notification('youtube-dl','Playlist download completed',os.path.join(addonFolder, "icon.png"),5000,True)
                return True


    def getYTID():
        ytid = False
        title = xbmc.getInfoLabel('Player.Title')
        YOUTUBE_VIDEO_URL = 'http://www.youtube.com/v/%s'

        if xbmc.Player().isPlaying():
            url = xbmc.Player().getPlayingFile()
            thumbnail = xbmc.getInfoLabel('Player.Art(thumb)')
            #year = xbmc.getInfoLabel('VideoPlayer.Year')
            if 'ytimg' in thumbnail:
                ytid = thumbnail.rsplit('/',2)
                ytid = ytid[-2]

        if not ytid:
            #Check if listitem property exists
            if not sys.listitem:
                xbmc.log('context.youtube.dl.menu: Could not obtain video id', xbmc.LOGERROR)
                return 1

            container=xbmc.getInfoLabel('container.folderpath')
            xbmc.log('context.youtube.dl.menu: '+'Container FolderPath: |%s|' % container, xbmc.LOGNOTICE)

            #Listitem exists, obtaining filename/url to extract video id
            #plugin_url = sys.listitem.getfilename()
            plugin_url = sys.listitem.getPath()
            #urldecoding url 5 times to account for nested addon-calls
            plugin_url = urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(plugin_url)))))
            xbmc.log('context.youtube.dl.menu: '+'ListItem.FileNameAndPath: |%s|' % plugin_url, xbmc.LOGNOTICE)
            if plugin_url:
                result = re.search('video_id=(?P<video_id>[a-zA-Z0-9_-]+)', plugin_url)
                if result:
                    xbmc.log('context.youtube.dl.menu: '+'Found video_id in url: |%s|' % result.group('video_id'), xbmc.LOGNOTICE)
                    video_id=result.group('video_id')
                else:
                    xbmc.log('context.youtube.dl.menu: '+'video_id not found in url '+plugin_url, xbmc.LOGERROR)
                    xbmcgui.Dialog().notification('youtube-dl error','video_id not found in url',os.path.join(addonFolder, "icon.png"),5000,True)
                    return 1

                if video_id:
                    ytid = video_id
                else:
                    xbmc.log('context.youtube.dl.menu: '+'video_id not found', xbmc.LOGERROR)
                    xbmcgui.Dialog().notification('youtube-dl error','video_id not found in url',os.path.join(addonFolder, "icon.png"),5000,True)
                    return 1
            else:
                xbmc.log('context.youtube.dl.menu: '+'Plugin URL not found', xbmc.LOGERROR)
                xbmcgui.Dialog().notification('youtube-dl error','url not found',os.path.join(addonFolder, "icon.png"),5000,True)
                return 1

            title = sys.listitem.getLabel()
            thumbnail = sys.listitem.getArt('thumb')

        url=YOUTUBE_VIDEO_URL % ytid

        #Debuginfo
        info = {'url': url, 'title': title, 'thumbnail': thumbnail, 'id': ytid, 'media_type': 'video'}
        LOG(repr(info), debug=True)

        return info

    def download(info=None,isPlaylist=False):
        global pDialog
        
        #Get url and title for individual download
        if info == None:
            LOG("Obtaining details", debug=True)
            info=main.getYTID()

        LOG(repr(info), debug=True)

        title=info['title']
        url=info['url']

        #Check if main target directory exists
        targetdir = getDownloadPath()
        if not xbmcvfs.exists(targetdir):
            LOG("Target directory does not exist!", debug=True)
            xbmcgui.Dialog().notification('youtube-dl error','destination path does not exist, check youtube-dl control configuration',os.path.join(addonFolder, "icon.png"),5000,True)
            return False
                        
        #checking if configured main target directory is writeable
        LOG("Checking if destination path "+targetdir+" is writeable", debug=True)
        f = xbmcvfs.File(os.path.join(targetdir, "koditmp.txt"), 'w')
        writeconfirm = f.write(str("1"))
        f.close()
        if writeconfirm:
            #cleaning up
            xbmcvfs.delete(os.path.join(targetdir, "koditmp.txt"))
            LOG("Destination path "+targetdir+" is writeable", debug=True)
        else:
            LOG("Destination path "+targetdir+" not writeable, aborting", debug=True)
            xbmcgui.Dialog().notification('youtube-dl error','destination path is not writeable',os.path.join(addonFolder, "icon.png"),5000,True)
            return False

#        yes = xbmcgui.Dialog().yesno('Continue downloading?', 'Download YouTube ID '+ytid+' ?', '')
        yes = True
        if yes:
            LOG("Downloading video with youtube-dl "+url, debug=True)

            if xbmc.Player().isPlaying():
                xbmcgui.Dialog().notification('youtube-dl download started',title,os.path.join(addonFolder, "icon.png"),5000,True)

            pDialog = xbmcgui.DialogProgressBG()

            if sys.version_info.major == 3:
                pDialog.create('YoutubeDL '+title, 'Preparing to download '+title+' ...')
            else:
                pDialog.create('YoutubeDL '+title.decode('latin1'), 'Preparing to download '+title.decode('latin1')+' ...')

            from youtube_dl.postprocessor import FFmpegPostProcessor
            ffm_ver = FFmpegPostProcessor()._versions
            LOG("FFmpeg/AVCONV versions: "+repr(ffm_ver), debug=True)

            #negative check as settings may not be set yet, thus defaulting to true
            if addon.getSetting("filename_upload_year") != "false":
                outtmpl_upload_year=' (%(upload_date).4s)'
            else:
                outtmpl_upload_year=''
                
            if addon.getSetting("filename_resolution") != "false":
                outtmpl_resolution='.%(height)sp'
            else:
                outtmpl_resolution=''
                
            ydl_opts = {
                'outtmpl': os.path.join(xbmc.translatePath('special://temp'))+'%(title)s'+outtmpl_upload_year+outtmpl_resolution+'.%(ext)s',
                'nopart': True,
#                'forcefilename': True,
                'logger': MyLogger(),
                }
            
            #Detailed download update only for individual videos, not during playlist download    
            if isPlaylist:
                ydl_opts.update( { "progress_hooks": [my_hook_empty] } )
            else:
                ydl_opts.update( { "progress_hooks": [my_hook] } )

            max_video_resolution = addon.getSetting("max_video_resolution")

            #if neither ffmpeg nor avconv is available, use best combined format
            if ffm_ver.get("avconv")==False and ffm_ver.get("ffmpeg")==False:
                ydl_opts.update( { "format": "best[height<="+max_video_resolution+"]" } )
            else:
                ydl_opts.update( { "format": "bestvideo[height<="+max_video_resolution+"]+bestaudio/best[height<="+max_video_resolution+"]" } )

            LOG("DEBUG YDL options: "+repr(ydl_opts), debug=True)

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl_info = ydl.extract_info(url,download=False)
                except youtube_dl.utils.ExtractorError as ee:
                    pDialog.close()
                    xbmc.log('context.youtube.dl.menu: '+'ExtractorError '+ee, xbmc.LOGERROR)
                    xbmcgui.Dialog().notification('youtube-dl error','YTD JS Error, check logs',os.path.join(addonFolder, "icon.png"),5000,True)
                    return False
                except youtube_dl.utils.DownloadError as de:
                    pDialog.close()
                    ERROR("Download error: {0}".format(de))
                    de = re.sub('.*YouTube said: ',  '', str(de))
                    xbmcgui.Dialog().notification('youtube-dl error','{0}'.format(de),os.path.join(addonFolder, "icon.png"),10000,True)
                    return False
                except:
                    #other YTD error, abort
                    pDialog.close()
                    xbmc.log('context.youtube.dl.menu: '+'Fatal error '+sys.exc_info()[0], xbmc.LOGERROR)
                    ERROR("Fatal YTD Error")
                    xbmcgui.Dialog().notification('youtube-dl error','Fatal YTD Error, check logs',os.path.join(addonFolder, "icon.png"),5000,True)
                    return False

                #ydl_formats = ydl.list_formats(ydl_info)
                #LOG("YTD Formats: "+repr(ydl_formats), debug=True)

                filename = ydl.prepare_filename(ydl_info)

                LOG("ydl_info: "+repr(ydl_info), debug=True)

                #set and create target sub directory if configured to use
                if isPlaylist==False and addon.getSetting("individual_uploader_directory") == "true":
                    LOG("Get uploader details", debug=True)
                    uploader=ydl_info['uploader']
                    LOG("Uploader = "+ydl_info['uploader'], debug=True)
                    targetdir = os.path.join(getDownloadPath(), uploader)
                    if not xbmcvfs.exists(targetdir):
                        LOG("Creating target directory", debug=True)
                        xbmcvfs.mkdirs(targetdir)
                        addon_created_new_dir = True
                elif isPlaylist==True and addon.getSetting("playlist_sub_directory") == "true":
                    LOG("Get playlist info", debug=True)
                    if 'playlist_title' in ydl_info:
                        playlistdir=ydl_info['playlist_title']
                    elif 'channel' in ydl_info:
                        playlistdir=ydl_info['channel']
                    else:
                        playlistdir=ydl_info['uploader']
                    LOG("Playlist info = "+playlistdir, debug=True)
                    targetdir = os.path.join(getDownloadPath(), playlistdir)
                    if not xbmcvfs.exists(targetdir):
                        LOG("Creating target directory", debug=True)
                        xbmcvfs.mkdirs(targetdir)
                        addon_created_new_dir = True
                else:
                    targetdir = getDownloadPath()

                #Check if file already downloaded - Note: May have different extension if format needs to be merged!
                LOG("Check if file already exists in target directory "+os.path.join(targetdir,os.path.basename(filename)), debug=True)
                if xbmcvfs.exists(os.path.join(targetdir,os.path.basename(filename))):
                    LOG("File already exists in target directory "+os.path.basename(filename), debug=True)
                    fileinfo_dst=xbmcvfs.Stat(os.path.join(targetdir,os.path.basename(filename)))
                    fileinfo_dst_size=fileinfo_dst.st_size
                    if fileinfo_dst_size == 0:
                        LOG("Existing file in target directory has filesize of 0, deleting and continue", debug=True)
                        xbmcvfs.delete(os.path.join(targetdir,os.path.basename(filename)))
                    else:
                        continuedownload = xbmcgui.Dialog().yesno('Continue downloading?', os.path.basename(filename)+' already exists!\nDelete and download again?', '')
                        if not continuedownload:
                            LOG("File already exist in target directory, not overwriting", debug=True)
                            pDialog.close()
                            xbmcgui.Dialog().notification('youtube-dl','Download cancelled',os.path.join(addonFolder, "icon.png"),5000,True)
                            return False
                        else:
                            LOG("Deleting existing file in target directory as requested", debug=True)
                            xbmcvfs.delete(os.path.join(targetdir,os.path.basename(filename)))

                #Continue downloading file
                if sys.version_info.major == 3:
                    pDialog.update(0, 'Downloading', 'Downloading '+title+' ...')
                    try:
                        ydl.process_ie_result(ydl_info, download=True)
                        pDialog.update(95, 'youtube-dl finished downloading '+title)
                        pDialog.update(98, 'youtube-dl moving file '+title)
                    except:
                        LOG("Download stalled", debug=True)
                        pDialog.close()
                        xbmcgui.Dialog().notification('youtube-dl','Download stalled ('+title+')',os.path.join(addonFolder, "icon.png"),5000,True)
                        return False
                else:
                    pDialog.update(0, 'Downloading', 'Downloading '+title.decode('latin1')+' ...')
                    try:
                        ydl.process_ie_result(ydl_info, download=True)
                        pDialog.update(95, 'youtube-dl finished downloading '+title.decode('latin1'))
                        pDialog.update(98, 'youtube-dl moving file '+title.decode('latin1'))
                    except:
                        LOG("Download stalled", debug=True)
                        pDialog.close()
                        xbmcgui.Dialog().notification('youtube-dl','Download stalled ('+title.decode('title1')+')',os.path.join(addonFolder, "icon.png"),5000,True)
                        return False

                #Recreating filename after download with proper extension
                base = os.path.splitext(filename)[0]
                filename = base + "." + finalformat

                if addon.getSetting('clean_filename') != 'false':
                    #cleaning filename
                    LOG("Cleaning up filename", debug=True)
                    repls = (' [Official Music Video]', ''), (' [Official Video]', ''), (' [OFFICIAL MUSIC VIDEO]', ''), (' [OFFICIAL VIDEO]', ''), \
                            (' (Official Music Video)', ''), (' (Official Video)', ''), (' (OFFICIAL MUSIC VIDEO)', ''), (' (OFFICIAL VIDEO)', ''), \
                            (' (Video)', ''), (' (VIDEO)', ''), \
                            (' [Video]', ''), (' [VIDEO]', ''),
                    newfilename = reduce(lambda a, kv: a.replace(*kv), repls, filename)
                    LOG("Filename now: "+newfilename, debug=True)
                    if xbmcvfs.rename(filename, newfilename):
                        filename = newfilename

                #Download complete, post actions
                while True:
                    LOG("post action loop begin", debug=True)
                    result = handleFinished(filename,title,targetdir,isPlaylist)
                    if result == False:
                        LOG("handlefinished false, retry query", debug=True)
                        if not xbmcvfs.exists(file_path):
                            LOG("Source file does not exists, abandon move attempt", debug=True)
                            LOG("breaking post action loop", debug=True)
                            xbmcgui.Dialog().notification('youtube-dl error','missing source file, check logs...',os.path.join(addonFolder, "icon.png"),5000,True)
                            break
                        retry = xbmcgui.Dialog().yesno('Move error','Failed to move '+filename+' to destination folder.\n\nTry again?','')
                        if not retry:
                            LOG("abandoned retry", debug=True)
                            delete = xbmcgui.Dialog().yesno('Move error - Delete temp file?','Failed to move\n'+os.path.basename(filename)+'\nto '+targetdir+'\nDelete temp file?','')
                            if delete:
                                LOG("delete temp file", debug=True)
                                xbmcvfs.delete(filename)
                                xbmcgui.Dialog().notification('youtube-dl deleted',title,os.path.join(addonFolder, "icon.png"),5000,True)
                                LOG("breaking post action loop", debug=True)
                            break
                        LOG("retrying", debug=True)
                    else:
                        LOG("post action loop end", debug=True)
                        break

                #cleanup
                if addon_created_new_dir == True and len(xbmcvfs.listdir(targetdir)) == 0:
                    LOG("Newly created target dir is empty, removing it", debug=True)
                    xbmcvfs.rmdir(targetdir)


def handleFinished(filename,title,targetdir,isPlaylist):
    global pDialog
    LOG("handlefinished function start", debug=True)
    LOG("final format "+finalformat, debug=True)
    if not finalformat == "":
        base = os.path.splitext(filename)[0]
        filename = base + "." + finalformat

    #Check if file already exists
    if xbmcvfs.exists(os.path.join(targetdir,os.path.basename(filename))):
        LOG("File already exists "+os.path.basename(filename), debug=True)
        fileinfo_dst=xbmcvfs.Stat(os.path.join(targetdir,os.path.basename(filename)))
        fileinfo_dst_size=fileinfo_dst.st_size
        if fileinfo_dst_size == 0:
            LOG("Existing file has filesize of 0, deleting and continue", debug=True)
            xbmcvfs.delete(os.path.join(targetdir,os.path.basename(filename)))
        else:
            LOG("Destination file already exists, not overwriting and aborting", debug=True)
            if sys.version_info.major == 3:
                pDialog.update(100, 'youtube-dl target file already exists'+title)
            else:
                pDialog.update(100, 'youtube-dl target file already exists'+title.decode('latin1'))
            xbmc.sleep(1000)
            pDialog.close()
            delete = xbmcgui.Dialog().yesno('Move error - Delete temp file?','Target file already exists.\n'+os.path.basename(filename)+'\nDelete temp file?','')
            if delete:
                xbmcvfs.delete(filename)
                xbmcgui.Dialog().notification('youtube-dl deleted',title,os.path.join(addonFolder, "icon.png"),5000,True)
            return True

    LOG("handlefinished movefile call", debug=True)
    if moveFile(filename,targetdir):
        LOG("File "+filename+" moved to "+targetdir, debug=True)
        if sys.version_info.major == 3:
            pDialog.update(100, 'youtube-dl file moved '+title)
        else:
            pDialog.update(100, 'youtube-dl file moved '+title.decode('latin1'))
        xbmc.sleep(1000)
        pDialog.close()
        if not isPlaylist:
            xbmcgui.Dialog().notification('youtube-dl finished',title,os.path.join(addonFolder, "icon.png"),5000,True)
        return True
    else:
        LOG("handlefinished movefile failed", debug=True)
        LOG("File "+os.path.basename(filename)+" could not be moved to "+targetdir, debug=True)
        if sys.version_info.major == 3:
            pDialog.update(100, 'youtube-dl file not moved '+title)
        else:
            pDialog.update(100, 'youtube-dl file not moved '+title.decode('latin1'))
        xbmc.sleep(1000)
        pDialog.close()
        return False


def moveFile(file_path, dest_path, filename=None):
    fname = filename or os.path.basename(file_path)
    destFilePath = os.path.join(dest_path, fname)

    LOG("Moving file "+fname+" from "+file_path+" to "+destFilePath, debug=True)
    if xbmcvfs.exists(file_path):
        LOG("Source file exists, proceeding", debug=True)
        if xbmcvfs.exists(destFilePath):
            fileinfo_dst=xbmcvfs.Stat(destFilePath)
            fileinfo_dst_size=fileinfo_dst.st_size()
            if fileinfo_dst_size == 0:
                LOG("Existing file has filesize of 0, deleting and continue", debug=True)
                xbmcvfs.delete(destFilePath)
            else:
                LOG("Destination file already exists, not overwriting and aborting", debug=True)
                return True

        #checking if configured target directory is writeable
        #f = xbmcvfs.File(os.path.join(targetdir, "koditmp.txt"), 'w')
        f = xbmcvfs.File(destFilePath+".txt", 'w')
        writeconfirm = f.write(str("1"))
        f.close()
        if writeconfirm:
          #cleaning up
          xbmcvfs.delete(destFilePath+".txt")
        else:
          LOG("Destination path "+destFilePath+" not writeable, aborting", debug=True)
          xbmcgui.Dialog().notification('youtube-dl move path not writeable',os.path.join(addonFolder, "icon.png"),5000,True)
          return False

        LOG("DEBUG: file path    "+file_path, debug=True)
        LOG("DEBUG: destFilePath "+destFilePath, debug=True)

        # xbmcvfs.copy(xbmc.translatePath(source), xbmc.translatePath(dest))
        copysuccess = False
        if xbmcvfs.copy(file_path, destFilePath):
            LOG ("Copied file to destination path", debug=True)
            copysuccess = True
        else:
            LOG ("Alternative copy method", debug=True)
            vidsrc = xbmcvfs.File(file_path, 'rb')
            vid_data = vidsrc.readBytes()
            vidsrc.close()
            LOG ("Video file read into memory", debug=True)
            viddst = xbmcvfs.File(destFilePath, 'wb')
            viddst.write(vid_data)
            viddst.close()
            LOG ("Video file written", debug=True)
            if xbmcvfs.exists(destFilePath):
                LOG ("File exists in destination folder", debug=True)
                fileinfo_src=xbmcvfs.Stat(file_path)
                fileinfo_src_size=fileinfo_src.st_size()
                fileinfo_dst=xbmcvfs.Stat(destFilePath)
                fileinfo_dst_size=fileinfo_dst.st_size()
                if fileinfo_src_size == fileinfo_dst_size:
                    LOG("File sizes match", debug=True)
                    copysuccess = True
                else:
                    LOG("File sizes do not match, copy failed. Source size = "+str(fileinfo_src_size)+", Destination size = "+str(fileinfo_dst_size), debug=True)
                    return False
            else:
                LOG ("File does NOT exist in destination folder", debug=True)

        if copysuccess:
            LOG("Copy successful, now deleting source file...", debug=True)
            if xbmcvfs.delete(file_path):
                LOG("Successfully deleted source file", debug=True)
                return True
            else:
                LOG("Could not delete source file", debug=True)
                return False
        else:
            LOG("xbmcvfs.copy failed", debug=True)
            return False
    else:
        LOG("Could not find source file "+file_path, debug=True)
        return False

