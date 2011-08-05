
# Import CherryPy global namespace
import cherrypy
import copy
import urllib
import urllib2
import urlparse
import os.path
import json

import conf.data
import httpls_client
import shaper

import conf

class DriplsController(object):
    '''DripLS Controller'''

    def on_start(self):
        pass

    def on_stop(self):
        pass

    def on_server_start(self):
        pass

    @cherrypy.expose
    def ostatus(self, s=None):
        """ Throw with a specified status """

        raise cherrypy.HTTPError(int(s), message="Custom error raised : {0}".format(s))

    @cherrypy.expose
    def cache_info(self, cid=None, r=None, tag=None, **kwargs):
        """ Cache and rewrite a m3u8 """

        info = self.cache_stream(cid, r, tag, kwargs)
        
        return json.dumps(info, sort_keys=True, indent=4)
   
    @cherrypy.expose
    def updatesegment(self, url, new_action):
        """ Update a previously shaped segment on the fly """

        shaper.update_shaped_segment(url, new_action)

        return "OK"
 
    @cherrypy.expose
    def master_m3u8(self, cid=None, r=None, tag=None, **kwargs):
        """ Cache and stream back a shaped playlist """

        cached_cid = self.cache_stream(cid, r, tag, kwargs)["id"]
 
        with open("{0}/playlists/m_{1}.m3u8".format(shaper.shaper_store_path, cached_cid), "r") as pf:
            master_content = pf.read()

        # return the rewritten master  
        cherrypy.response.headers['Content-Type'] = "application/vnd.apple.mpegurl"
        cherrypy.response.headers['Content-Disposition'] = "inline; filename={0}.m3u8".format(cid)

        return master_content

    @cherrypy.expose
    def playlist_m3u8(self, p=None, **kwargs):
        """ Stream back a cached playlist """

        with open("{0}/playlists/{1}.m3u8".format(shaper.shaper_store_path,p), "r") as pf:
            playlist_content = pf.read()

        cherrypy.response.headers['Content-Type'] = "application/vnd.apple.mpegurl"
        cherrypy.response.headers['Content-Disposition'] = "inline; filename={0}.m3u8".format(p)

        return playlist_content

    @cherrypy.expose
    def tag_m3u8(self, tag=None, **kwargs):
        """ Do the shaping off of a pre-made tag """

        with open("{0}/playlists/tag_{1}".format(shaper.shaper_store_path, tag) , "r") as pf: 
            tag_qs = pf.read()

        #add old keys
        tag_args = urlparse.parse_qs(tag_qs)
        for key in tag_args:
            tag_args[key] = tag_args[key][0]

        #add any new kes that we might have gotten(some might override old keys)
        for key in kwargs:
            tag_args[key] = kwargs[key]
  
        #run master with the tag args
        return self.master_m3u8(**tag_args);

    def cache_stream(self, cid=None, r=None, tag=None, kwargs=None):
        """ Perform the actual caching and shaping  of the stream """

        rules = shaper.parse_rules(r)

        seeded_content_id = conf.common.get_seeded_cid(cid)
        master_playlist = conf.data.provider.pull_master_m3u8(cid, kwargs)

        info = shaper.cache_and_shape(master_playlist, seeded_content_id, rules)
        info["url"] = conf.common.get_final_url("playlist.m3u8","p=m_{0}".format(seeded_content_id))

        # if we have a tag, store
        if tag:
            self.store_tag(cid, r, tag, kwargs)

        return info

    def store_tag(self, cid, r, tag, kwargs):
        """ Store all arguments recieved on the url as the associated tag """
        tag_args = conf.data.provider.get_tag_kwargs(kwargs)
        tag_args["cid"] = cid

        if r:
            tag_args["r"] = r

        with open("{0}/playlists/tag_{1}".format(shaper.shaper_store_path, tag), "w") as pf:
            pf.write("{0}".format(urllib.urlencode(tag_args)))
  
conf.dripls_main_site_url = conf.app['root_url']
root = DriplsController()

current_path = os.path.dirname(os.path.abspath(__file__))
 
app_config = {
    '/playlists': {
         'tools.staticdir.on': True,
         'tools.staticdir.dir': os.path.join(shaper.shaper_store_path, 'playlists'),
         'tools.staticdir.content_types': {
             'ts': 'video/mp2t',
             'm3u8': 'application/vnd.apple.mpegurl'
         }
    }
}
    
cherrypy.config.update({
    'log.error_file': conf.error_log,
    'log.screen': True
})

app = cherrypy.tree.mount(root, '/', app_config)