"""Reusable admin form widgets, shared by every app's admin.

The only one so far is the location picker: Contact settings (and Hotels) store
latitude/longitude, and asking an administrator to type coordinates by hand is
error prone. This widget pairs a searchable, draggable OpenStreetMap map with the
model's own latitude/longitude inputs.
"""

from django import forms


class LocationMapWidget(forms.Widget):
    """Leaflet + OpenStreetMap picker bound to the ``latitude``/``longitude`` inputs.

    Render it as the *last* field of a fieldset so the two number inputs already
    exist in the DOM when the picker's script initialises.

    The template lives in ``content/templates/contact/`` because form widgets are
    rendered by the *forms* renderer, which only searches app template folders.
    """

    template_name = 'contact/location_map.html'

    class Media:
        css = {'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)}
        js = ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['lat_input_id'] = 'id_latitude'
        context['widget']['lng_input_id'] = 'id_longitude'
        return context
