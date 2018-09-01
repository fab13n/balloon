"use strict"

import "babel-polyfill"; /* Enable async/await keywords. */
import * as d3 from 'd3';

import Map from 'ol/map';
import View from 'ol/view';
import TileLayer from 'ol/layer/tile';
import XYZ from 'ol/source/xyz';
import VectorSource from 'ol/source/vector';
import VectorLayer from 'ol/layer/vector';
import GeoJSON from 'ol/format/geojson';
import Style from 'ol/style/style';
import Stroke from 'ol/style/stroke';
import Fill from 'ol/style/fill';
import CircleStyle from 'ol/style/circle';
import Point from 'ol/geom/point'
import proj from 'ol/proj';

window.d3 = d3;

/**
 * A random identifier allowing to attach progress reports with trajectory requests.
 */
const id = Math.random().toString(36).substr(2, 9);
d3.select('[name=id]').property('value', id);

/**
 * Extract URL parameters.
 */
function get_url_params() {
    let url_params = {};
    if (window.location.href.includes("?")) {
        window.location.href.split("?")[1].split("&")
            .map(p => p.split("="))
            .forEach(p => url_params[decodeURIComponent(p[0])] = decodeURIComponent(p[1]));
    }
    return url_params;
}

const url_params = get_url_params();

/* Where GeoJSON trajectories will be displayed. */
let trajectory_style = new Style({
    stroke: new Stroke({color: 'green', width: 3}),
    image: new CircleStyle({
        radius: 6,
        stroke: new Stroke({color: "green", width: 2}),
        fill: new Fill({color: "white"})})});
let trajectory_source = new VectorSource();
let map = new Map({
    target: 'map',
    view: new View({center: proj.fromLonLat([1.4855, 43.5489]), zoom: 10, maxZoom: 19}),
    layers: [
        new TileLayer({source: new XYZ({url: 'https://{a-c}.tile.openstreetmap.org/{z}/{x}/{y}.png'})}),
        new VectorLayer({source: trajectory_source, style: trajectory_style})]});

window.map = map;

/**
 * Draw a GeoJSON feature on a map.
 */
function display_trajectory(geoJSON) {
    trajectory_source.clear();
    // Enrich properties with point coordinates in degrees (in the geometry they will be reprojected).
    geoJSON.features.forEach(ftr => { ftr.properties.coordinates = ftr.geometry.coordinates; });
    let point_features = new GeoJSON({
        defaultDataProjection: 'EPSG:4326',
        featureProjection: map.getView().getProjection()
    }).readFeatures(geoJSON);
    // Generate a LineString with vertexes at each point, to connect the dots visually.
    let linestring_feature = new GeoJSON({
        defaultDataProjection: 'EPSG:4326',
        featureProjection: map.getView().getProjection()
    }).readFeatures({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": geoJSON.features.map(ftr => ftr.geometry.coordinates)}});
    trajectory_source.addFeatures(linestring_feature);
    trajectory_source.addFeatures(point_features);
    map.getView().fit(trajectory_source.getExtent(), map.getSize());
}


async function update_available_dates() {
    let model_name = d3.select('[name=model]').property('value');
    let url = `/forecast/list/${model_name}`;
    if(url_params['from']) { url += `?from=${url_params['from']}`; }
    let response = await fetch(url);
    let dates = await response.json();
    let date_pairs = Object.getOwnPropertyNames(dates).map(key => [key, dates[key]]).sort();
    // d3.selectAll(`[name=date] option`).remove();
    d3.select(`[name=date]`).selectAll(`option`).data(date_pairs).enter()
        .append('option')
        .attr('value', p => p[0])
        .attr('disabled', p => p[1] === false ? 'disabled' : null)
        .text(p => p[0]);
    // select first non-disabled date
    let first_valid_option=d3.select("[name=date] option:not([disabled])");
    if(! first_valid_option.empty()) {
        d3.select("[name=date]").property("value",  first_valid_option.attr("value"));
    }
}

window.update_available_dates = update_available_dates;

async function update_trajectory() {
    const names=['id', 'model', 'date', 'latitude', 'longitude', 'balloon_mass_kg', 'payload_mass_kg', 'ground_volume_m3'];
    let values = names.map(name => name + '=' + d3.select(`[name=${name}]`).property('value'));
    let url = '/trajectory?' + values.join('&');
    let response = await fetch(url);
    let geojson = await response.json();
    console.log(geojson);
    display_trajectory(geojson);
}

function update_suggestions() {
    const HE_LIFT_KG_M3 = .025/.0224;
    const G_M_S2 = 9.81;
    const SUGGESTED_LIFT_N = { 0.5: 15, 1: 16, 1.2: 17, 2: 18}; // Balloon mass => suggested_lift
    let balloon_mass_kg = Number(d3.select('[name=balloon_mass_kg]').property('value'));
    let payload_mass_kg = Number(d3.select('[name=payload_mass_kg]').property('value'));
    let ground_volume_m3 = Number(d3.select('[name=ground_volume_m3]').property('value'));
    let weight = (balloon_mass_kg + payload_mass_kg) * G_M_S2;
    let suggested_lift = SUGGESTED_LIFT_N[balloon_mass_kg];
    let suggested_volume = (weight + suggested_lift) / G_M_S2 / HE_LIFT_KG_M3;
    let lift = ground_volume_m3 * HE_LIFT_KG_M3 * G_M_S2 - weight;
    d3.select('#suggested_lift').text(suggested_lift);
    d3.select('#suggested_volume').text(suggested_volume.toFixed(2));
    d3.select('#suggested_payload_mass').text('2.5');
    d3.select('#lift').text(lift.toFixed(2));
}

function display_feature_details(ftr) {
    if(ftr === null) {
        d3.select(".position_details").style("display", "none");
    } else {
        d3.select(".position_details").style("display", null);
        console.log("---------------");
        let properties = ftr.getProperties();
        Object.getOwnPropertyNames(properties).forEach((name) => {
            let value = properties[name];
            if (value instanceof Object) {
                Object.getOwnPropertyNames(value).forEach((sub_name) => {
                    let sub_value = value[sub_name];
                    console.log(`${name}_${sub_name} = ${sub_value}`);
                    d3.select(`.position_details .${name}_${sub_name}`).text(sub_value);
                });
            } else {
                console.log(`${name} = ${value}`);
                d3.select(`.position_details .${name}`).text(value);
            }
        });
    }
}

window.update_trajectory = update_trajectory;

update_available_dates();
update_suggestions();

d3.select('[name=download_forecast]')
    .on('click', () => { window.location='download_forecast.html'; });
d3.select('[name=update_trajectory]')
    .on('click', update_trajectory);
d3.selectAll('.impacts_suggestions')
    .on('click change keypress', update_suggestions);
map.on('pointermove', (evt) => {
    let feature = null;
    map.forEachFeatureAtPixel(evt.pixel, ftr => { if(ftr.getGeometry() instanceof Point) { feature = ftr; }});
    display_feature_details(feature); // feature may be null
});
display_feature_details(null);