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
_ = g15locale.get_translation("bitcoin-ticker", modfile = __file__).ugettext

import gnome15.g15screen as g15screen 
import gnome15.g15theme as g15theme 
import gnome15.g15util as g15util
import gnome15.g15driver as g15driver
import gnome15.g15globals as g15globals
import gnome15.g15text as g15text
import gnome15.g15plugin as g15plugin
import datetime
import gtk
import pango
import os
import locale
import ticker

# Plugin details - All of these must be provided
id="bitcoin-ticker"
name=_("Bitcoin Ticker")
description=_("Displays information about the current bitcoin exchange rate")
author="Alfie \"Azelphur\" Day <support@azelphur.com>"
copyright=_("Copyright (C)2013 Alfie Day")
site="http://azelphur.com"
has_preferences=True
unsupported_models = [ g15driver.MODEL_G110, g15driver.MODEL_G11, g15driver.MODEL_G930, g15driver.MODEL_G35 ]


''' 
This function must create your plugin instance. You are provided with
a GConf client and a Key prefix to use if your plugin has preferences
'''
def create(gconf_key, gconf_client, screen):
    return G15BitcoinTicker(gconf_key, gconf_client, screen)

''' 
This function must be provided if you set has_preferences to True. You
should display a dialog for editing the plugins preferences
'''
def show_preferences(parent, driver, gconf_client, gconf_key):
    G15BitcoinTickerPreferences(parent, driver, gconf_key, gconf_client)

class G15BitcoinTickerPreferences():
    
    def __init__(self, parent, driver, gconf_key, gconf_client):
        widget_tree = gtk.Builder()
        widget_tree.add_from_file(os.path.join(os.path.dirname(__file__), "bitcoin-ticker.glade"))
        
        dialog = widget_tree.get_object("TickerDialog")
        dialog.set_transient_for(parent)
        
        exchange_model = widget_tree.get_object("ExchangeModel")
        exchange_combo_box = widget_tree.get_object("ExchangeComboBox")

        currency_model = widget_tree.get_object("CurrencyModel")
        currency_combo_box = widget_tree.get_object("CurrencyComboBox")

        update_minutes_spin_button = widget_tree.get_object("UpdateMinutesSpinButton")

        def _exchange_changed(widget, key):
            exchange = exchange_model[widget.get_active()][0]
            gconf_client.set_string(key, exchange)

            currency_model.clear()

            currencies = ticker.getCurrencies(exchange)

            selected_currency = gconf_client.get_string(gconf_key + "/currency")
            if selected_currency == None or selected_currency not in currencies:
                selected_currency = currencies[0]

            for currency in currencies:
                currency_model.append([currency])
                if currency == selected_currency:
                    currency_combo_box.set_active(len(currency_model) - 1)
        
        def _currency_changed(widget, key):
            slot = widget.get_active()
            if slot == -1: return
            currency = currency_model[slot][0]
            gconf_client.set_string(key, currency)

        def _update_minutes_changed(widget, key):
            gconf_client.set_int(key, int(widget.get_value()))
            
        exchange_combo_box.connect("changed", _exchange_changed, gconf_key + "/exchange")
        currency_combo_box.connect("changed", _currency_changed, gconf_key + "/currency")
        update_minutes_spin_button.connect("value-changed", _update_minutes_changed, gconf_key + "/update_minutes")
        update_minutes = gconf_client.get_int(gconf_key + "/update_minutes")
        if update_minutes == None:
            update_minutes = 30
        update_minutes_spin_button.set_value(update_minutes)

        exchanges = ticker.getExchanges()

        selected_exchange = gconf_client.get_string(gconf_key + "/exchange")
        if selected_exchange == None or selected_exchange not in exchanges:
            selected_exchange = exchanges[0]

        for exchange in exchanges:
            exchange_model.append([exchange])
            if exchange == selected_exchange:
                exchange_combo_box.set_active(len(exchange_model) - 1)

        dialog.run()
        dialog.hide()


def _changed(widget, key, gconf_client):
    '''
    gconf configuration has changed, redraw our canvas
    '''
    gconf_client.set_bool(key, widget.get_active())

class G15BitcoinTicker(g15plugin.G15Plugin):
    '''
    You would normally want to extend at least g15plugin.G15Plugin as it
    provides basic plugin functions. 
    
    There are also further specialisations, such as g15plugin.G15PagePlugin
    for plugins that have display a page, or g15plugin.G15MenuPlugin for
    menu like plugins, or g15plugin.G15RefreshingPlugin for plugins that
    refresh their view based on a timer.
    
    This example uses the most basic type to demonstrate how plugins are put
    together, but it could easily use G15RefreshingPlugin and cut out a lot
    of code.
    
    '''
    
    
    ''' 
    ******************************************************************
    * Lifecycle functions. You must provide activate and deactivate, *
    * the constructor and destroy function are optional              *
    ******************************************************************
    '''
    
    def __init__(self, gconf_key, gconf_client, screen):
        g15plugin.G15Plugin.__init__(self, gconf_client, gconf_key, screen)
        self.hidden = False
        self.page = None
        self._last_update = 0
        self.exdata = None
    
    def activate(self):
        '''
        The activate function is invoked when gnome15 starts up, or the plugin is re-enabled
        after it has been disabled. When extending any of the provided base plugin classes,
        you nearly always want to call the function in the supoer class as well
        '''
        g15plugin.G15Plugin.activate(self)
        

        '''
        Load our configuration
        '''        
        self.timer = None
        self._load_configuration()
        
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
                                     thumbnail_painter = self.paint_thumbnail, panel_painter = self.paint_thumbnail,
                                     theme = self.theme,
                                     originating_plugin = self)

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

        self._refresh()
        self.bitcoinLogo = g15util.load_surface_from_file(os.path.join(os.path.dirname(__file__), "bitcoinLogo.svg"))
        
        '''
        Schedule a bitcoin rate update
        '''        
        self._schedule_refresh()
        
        '''
        We want to be notified when the plugin configuration changed, so watch for gconf events.
        The watch function is used, as this will automatically track the monitor handles
        and clean them up when the plugin is deactivated
        '''        
        self.watch(None, self._config_changed)
    
    def deactivate(self):
        g15plugin.G15Plugin.deactivate(self)
        
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
        if self.page != None and self.screen.driver.get_bpp() == 16:
            return g15util.paint_thumbnail_image(allocated_size, self.bitcoinLogo, canvas)
    
    ''' 
    ***********************************************************
    * Functions specific to plugin                            *
    ***********************************************************    
    ''' 
        
    def _config_changed(self, client, connection_id, entry, args):
        
        '''
        Load the gconf configuration
        '''
        last = [self.exchange, self.currency]
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
        
        
        '''
        Schedule a redraw as well
        '''

        if last == [self.exchange, self.currency]:
            self._schedule_refresh()
        else:
            self._refresh()
        
    def _load_configuration(self):
        self.exchange = self.gconf_client.get_string(self.gconf_key + "/exchange")
        if self.exchange == None:
            self.exchange = ticker.getExchanges()[0]

        self.currency = self.gconf_client.get_string(self.gconf_key + "/currency")
        if self.currency == None:
            self.currency = ticker.getCurrencies(self.exchange)[0]

        self.update_minutes = self.gconf_client.get_int(self.gconf_key + "/update_minutes")
        if self.update_minutes == None:
            self.update_minutes = 30

    def _refresh(self):
        '''
        Invoked by the timer once a second to redraw the screen. If your page is currently activem
        then the paint() functions will now get called. When done, we want to schedule the next
        redraw
        '''
        self.exdata = ticker.getRate(self.exchange, self.currency)
        self.screen.redraw(self.page) 
        self._schedule_refresh()
        
    def _schedule_refresh(self):
        if not self.active:
            return

        if self.timer is not None:
            self.timer.cancel()

        '''
        Determine when to schedule the next redraw for. 
        '''
        now = datetime.datetime.now()
        next_tick = now + datetime.timedelta(0, self.update_minutes * 60)
        next_tick = datetime.datetime(next_tick.year,next_tick.month,next_tick.day,next_tick.hour, next_tick.minute, 0)
        delay = g15util.total_seconds( next_tick - now )
        
        '''
        Try not to create threads or timers if possible. Use g15util.schedule() instead
        '''
        self.timer = g15util.schedule("BitcoinTickerRedraw", delay, self._refresh)
        
    def _reload_theme(self):        
        self.theme = g15theme.G15Theme(os.path.join(os.path.dirname(__file__), "default"))
        
    '''
    Get the properties dictionary
    '''
    def _get_properties(self):
        properties = { }
        
        '''
        Get the details to display and place them as properties which are passed to
        the theme
        '''
        properties["exchange"] = self.exchange
        properties["currency"] = self.currency
        icon = os.path.join(os.path.dirname(__file__), "icons", self.exchange+".svg")
        if os.path.exists(icon):
            properties["icon"] = icon
        else:
            properties["icon"] = os.path.join(os.path.dirname(__file__), "bitcoinLogo.svg")
        if self.exdata == None:
            return properties

        for k, v in self.exdata.items():
            properties[k] = v

        properties["volume"] = round(properties["volume"], 2)
        return properties
