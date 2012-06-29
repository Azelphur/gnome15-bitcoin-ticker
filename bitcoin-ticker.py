#        +-----------------------------------------------------------------------------+
#        | GPL                                                                         |
#        +-----------------------------------------------------------------------------+
#        | Copyright (c) Brett Smith <tanktarta@blueyonder.co.uk>                      |
#        |                                                                             |
#        | This program is free software; you can redistribute it and/or               |
#        | modify it under the terms of the GNU General Public License                 |
#        | as published by the Free Software Foundation; either version 2              |
#        | of the License, or (at your option) any later version.                      |
#        |                                                                             |
#        | This program is distributed in the hope that it will be useful,             |
#        | but WITHOUT ANY WARRANTY; without even the implied warranty of              |
#        | MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               |
#        | GNU General Public License for more details.                                |
#        |                                                                             |
#        | You should have received a copy of the GNU General Public License           |
#        | along with this program; if not, write to the Free Software                 |
#        | Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA. |
#        +-----------------------------------------------------------------------------+
 
import gnome15.g15locale as g15locale
_ = g15locale.get_translation("clock", modfile = __file__).ugettext

import gnome15.g15screen as g15screen 
import gnome15.g15theme as g15theme 
import gnome15.g15util as g15util
import gnome15.g15driver as g15driver
import gnome15.g15globals as g15globals
import gnome15.g15text as g15text
import datetime
import gtk
import pango
import os
import locale
import libticker

# Plugin details - All of these must be provided
id="bitcoin-ticker"
name=_("Bitcoin Ticker")
description=_("Displays current bitcoin exchange rate")
author="Alfie \"Azelphur\" Day <support@azelphur.com>"
copyright=_("Copyright (C)2010 Alfie Day")
site="http://www.gnome15.org/"
has_preferences=True
unsupported_models = [ g15driver.MODEL_G110, g15driver.MODEL_G11 ]

# 
# This simple plugin displays a digital clock. It also demonstrates
# how to add a preferences dialog for your plugin
# 

''' 
This function must create your plugin instance. You are provided with
a GConf client and a Key prefix to use if your plugin has preferences
'''
def create(gconf_key, gconf_client, screen):
    return BitcoinTicker(gconf_key, gconf_client, screen)

def show_preferences(parent, driver, gconf_client, gconf_key):
    widget_tree = gtk.Builder()
    widget_tree.add_from_file(os.path.join(os.path.dirname(__file__), "bitcoin-ticker.glade"))
    
    dialog = widget_tree.get_object("ClockDialog")
    dialog.set_transient_for(parent)

    exchange_model = widget_tree.get_object("ExchangeModel")
    exchange_combo_box = widget_tree.get_object("ExchangeComboBox")
    exchange_combo_box.connect("changed", exchange_changed, gconf_key + "/exchange", [gconf_client, exchange_model])

    selected_exchange = gconf_client.get_string(gconf_key + "/exchange")
    exchanges = libticker.getExchanges()
    if selected_exchange == None:
        selected_exchange = exchanges[0]
    for exchange in exchanges:
        exchange_model.append([exchange])
        if exchange == selected_exchange:
            exchange_combo_box.set_active(len(exchange_model) - 1)


    exchange_spin_button = widget_tree.get_object("UpdateMinutesSpinButton")
    adj = gtk.Adjustment(1, 1, 9999, 1, 1, 1)
    exchange_spin_button.configure(adj, 1, 0)
    exchange_spin_button.connect("value-changed", time_changed, gconf_key + "/update_minutes", gconf_client)
    update_minutes = gconf_client.get_int(gconf_key + "/update_minutes")
    if update_minutes == None:
        update_minutes = 15
    exchange_spin_button.set_value(update_minutes)

    exchange_combo_box = widget_tree.get_object("label1")
    exchange_combo_box = widget_tree.get_object("label2")
        
    dialog.run()
    dialog.hide()

def time_changed(widget, key, gconf_client):
    gconf_client.set_int(key, int(widget.get_value()))

def exchange_changed(widget, key, args):
    gconf_client = args[0]
    model = args[1]
    gconf_client.set_string(key, model[widget.get_active()][0])

class BitcoinTicker():
    
    ''' 
    ******************************************************************
    * Lifecycle functions. You must provide activate and deactivate, *
    * the constructor and destroy function are optional              *
    ******************************************************************
    '''
    
    def __init__(self, gconf_key, gconf_client, screen):
        self.screen = screen
        self.hidden = False
        self.gconf_client = gconf_client
        self.gconf_key = gconf_key
        self.page = None
        self.exchange = None
    
    def activate(self):
        
        '''
        The activate function is invoked when gnome15 starts up, or the plugin is re-enabled
        after it has been disabled
        '''
        
        self.timer = None
        self._load_configuration()
        
        '''
        We will be drawing text manually in the thumbnail, so it is recommended you use the
        G15Text class which simplifies drawing and measuring text in an efficient manner  
        '''
        self.text = g15text.new_text(self.screen)
        
        '''
        Most plugins will delegate their drawing to a 'Theme'. A theme usually consists of an SVG file, one
        for each model that is supported, and optionally a fragment of Python for anything that can't
        be done with SVG and the built in theme facilities
        '''
        self._reload_theme()
        
        '''
        Most plugins will usually want to draw on the screen. To do so, a 'page' is created. We also supply a callback here to
        perform the painting. You can also supply 'on_shown' and 'on_hidden' callbacks here to be notified when your
        page actually gets shown and hidden.
        
        A thumbnail painter function is also provided. This is used by other plugins want a thumbnail representation
        of the current screen. For example, this could be used in the 'panel', or the 'menu' plugins
        '''        
        self.page = g15theme.G15Page("Bitcoin Ticker", self.screen, 
                                     theme_properties_callback = self._get_properties,
                                     theme = self.theme)
                                     #thumbnail_painter = self.paint_thumbnail, panel_painter = self.paint_thumbnail,
        self.page.title = "Bitcoin Ticker"
        
        '''
        Add the page to the screen
        '''
        self.screen.add_page(self.page)
        
        ''' 
        Once created, we should always ask for the screen to be drawn (even if another higher
        priority screen is actually active. If the canvas is not displayed immediately,
        the on_shown function will be invoked when it finally is.         
        '''
        self.screen.redraw(self.page)
        
        '''
        As this is a Clock, we want to redraw at fixed intervals. So, schedule another redraw
        if appropriate
        '''        
        self._schedule_redraw()
        
        '''
        We want to be notified when the plugin configuration changed, so watch for gconf events
        '''        
        self.notify_handle = self.gconf_client.notify_add(self.gconf_key, self._config_changed);
    
    def deactivate(self):
        
        '''
        Stop being notified about configuration changes
        '''        
        self.gconf_client.notify_remove(self.notify_handle);
        
        '''
        Stop updating
        '''
        if self.timer != None:
            self.timer.cancel()
            self.timer = None
        
        ''' 
        Deactivation occurs when either the plugin is disabled, or the applet is stopped
        On deactivate, we must remove our canvas.  
        '''        
        self.screen.del_page(self.page)
        
    def destroy(self):
        '''
        Invoked when the plugin is disabled or the applet is stopped
        '''
        pass
    
    ''' 
    **************************************************************
    * Common callback functions. For example, your plugin is more* 
    * than likely to want to draw something on the LCD. Naming   *
    * the function paint() is the convention                     *
    **************************************************************    
    '''
        
    '''
    Paint the thumbnail. You are given the MAXIMUM amount of space that is allocated for
    the thumbnail, and you must return the amount of space actually take up. Thumbnails
    can be used for example by the panel plugin, or the menu plugin. If you want to
    support monochrome devices such as the G15, you will have to take into account
    the amount of space you have (i.e. 6 pixels high maximum and limited width)
    ''' 
    def paint_thumbnail(self, canvas, allocated_size, horizontal):
        if self.page and not self.screen.is_visible(self.page):
            properties = self._get_properties()
            # Don't display the date or seconds on mono displays, not enough room as it is
            if self.screen.driver.get_bpp() == 1:
                text = properties["time_nosec"]
                font_size = 8
                factor = 2
                font_name = g15globals.fixed_size_font_name
                x = 1
                gap = 1
            else:
                factor = 1 if horizontal else 2
                font_name = "Sans"
                if self.display_date:
                    text = "%s\n%s" % ( properties["time"],properties["date"] ) 
                    font_size = allocated_size / 3
                else:
                    text = properties["time"]
                    font_size = allocated_size / 2
                x = 4
                gap = 8
                
            self.text.set_canvas(canvas)
            self.text.set_attributes(text, align = pango.ALIGN_CENTER, font_desc = font_name, \
                                     font_absolute_size = font_size * pango.SCALE / factor)
            x, y, width, height = self.text.measure()
            if horizontal: 
                if self.screen.driver.get_bpp() == 1:
                    y = 0
                else:
                    y = (allocated_size / 2) - height / 2
            else:      
                x = (allocated_size / 2) - width / 2
                y = 0
            self.text.draw(x, y)
            if horizontal:
                return width + gap
            else:
                return height + 4
    
    ''' 
    ***********************************************************
    * Functions specific to plugin                            *
    ***********************************************************    
    ''' 
        
    def _config_changed(self, client, connection_id, entry, args):
        
        '''
        Load the gconf configuration
        '''
        self._load_configuration()
        
        '''
        This is called when the gconf configuration changes. See add_notify and remove_notify in
        the plugin's activate and deactive functions.
        '''
        
        '''
        Reload the theme as the layout required may have changed (i.e. with the 'show date' 
        option has been change)
        '''
        self._reload_theme()
        self.page.set_theme(self.theme)
        
        '''
        In this case, we temporarily raise the priority of the page. This will force
        the page to be painted (i.e. the paint function invoked). After the specified time,
        the page will revert it's priority. Only one revert timer is active at any one time,
        so it is safe to call this function in quick succession  
        '''
        self.screen.set_priority(self.page, g15screen.PRI_HIGH, revert_after = 3.0)
        
    def _load_configuration(self):
        update = False
        if self.exchange != None:
            update = True

        self.exchange = self.gconf_client.get_string(self.gconf_key + "/exchange")
        if self.exchange == None:
            self.exchange = libticker.getExchanges()[0]

        self.update_minutes = self.gconf_client.get_int(self.gconf_key + "/update_minutes")

        if update:
            self._update_rate()
        
    def _redraw(self):
        '''
        Invoked by the timer once a second to redraw the screen. If your page is currently activem
        then the paint() functions will now get called. When done, we want to schedule the next
        redraw
        '''
        self.screen.redraw(self.page) 
        self._schedule_redraw()
        
    def _schedule_redraw(self):
        '''
        Determine when to schedule the next redraw for. 
        '''
        self._update_rate()
        
        '''
        Try not to create threads or timers if possible. Use g15util.schedule() instead
        '''
        self.timer = g15util.schedule("BitcoinTickerUpdate", self.update_minutes*60, self._redraw)
        
    def _reload_theme(self):
        self.theme = g15theme.G15Theme(os.path.join(os.path.dirname(__file__), "default"), self.exchange.lower())
                
    '''
    Get the properties dictionary
    '''
    def _get_properties(self):
        properties = { }
        
        '''
        Get the details to display and place them as properties which are passed to
        the theme
        '''
        properties["rate"] = self.exchangerate
            
        return properties

    def _update_rate(self):
        self.exchangerate = libticker.getRate(self.exchange)
