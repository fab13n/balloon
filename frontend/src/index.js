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
import ScaleLine from 'ol/control/scaleline';
import proj from 'ol/proj';
import RainbowGenerator from 'color-rainbow';
import numeral from 'numeral';

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

/* Altitude legend and scale */
const NB_OF_COLORS = 32;
const MAX_ALTITUDE = 40000; // meters
const rainbow = d3.scaleLinear()
    .domain(d3.range(NB_OF_COLORS).map(x => x * MAX_ALTITUDE / (NB_OF_COLORS-1)))
    .range(RainbowGenerator.create(NB_OF_COLORS).map(c => c.hexString()));
d3.select("#legend")
    .selectAll("div.item").data(rainbow.domain().reverse()).enter()
    .append('div')
    .attr('class', 'item')
    .style('background-color', n=>rainbow(n))
    .style('height', `${d3.select("#legend").node().getBoundingClientRect().height/NB_OF_COLORS}px`)
    .text(n=>numeral(n).format('0a')+'m');


let trajectory_style = (ftr) => {
    let p = ftr.getProperties();
    let circle_color = p.position ? rainbow(p.position.z) : 'green';
    return new Style({
        stroke: new Stroke({color: 'green', width: 3}),
        image: new CircleStyle({
            radius: 6,
            stroke: new Stroke({color: circle_color, width: 2}),
            fill: new Fill({color: "white"})})});
};

/* Where GeoJSON trajectories will be displayed. */
let trajectory_source = new VectorSource();
let map = new Map({
    target: 'map',
    view: new View({center: proj.fromLonLat([1.4855, 43.5489]), zoom: 10, maxZoom: 19}),
    layers: [
        new TileLayer({source: new XYZ({url: 'https://{a-c}.tile.openstreetmap.org/{z}/{x}/{y}.png'})}),
        new VectorLayer({source: trajectory_source, style: trajectory_style})]});
map.addControl(new ScaleLine({units: 'metric'}));
window.map = map;

/**
 * Draw a GeoJSON feature on a map.
 */
function display_trajectory(geoJSON) {
    trajectory_source.clear();
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

function draw_point(p) {
    const CIRCLE_RADIUS = 10;
    const ALTITUDE_SCALE = MAX_ALTITUDE / 100;

    //const ARROW_HEAD_LENGTH = 10;
    //const ARROW_HEAD_ANGLE = Math.PI/6;
    //const SPEED_SCALE = 5;

    let px2c = (coords) =>
        map.getView().getCoordinateFromPixel(coords);
    let balloon_circle_style = (ftr) => {
        let p = ftr.getProperties();
        return new Style({
            image: new CircleStyle({
                radius: CIRCLE_RADIUS,
                stroke: new Stroke({color: rainbow(p.position.z), width: 2}),
                fill: new Fill({color: "white"})})});
    };
    let balloon_height_style = (ftr) => {
        let p = ftr.getProperties();
        return new Style({
            stroke: new Stroke({color: rainbow(p.position.z), width: 3}),
            text: new Text({
                text: p.label,
                placement: 'point',
                offsetY: 5,
                textAlign: 'center',
                textBaseline: 'top',
                fill: rainbow(p.position.z)})});
    };
    let ground_c = proj.transform([p.position.x, p.position.y], 'EPSG:4326', map.getView().getProjection());
    let ground_px = map.getPixelFromCoordinate(ground_c);
    let circle_center_px = [ground_px[0], ground_px[1] - p.position.z * ALTITUDE_SCALE];
    let circle_bottom_px = [circle_center_px[0], circle_center_px[1] - CIRCLE_RADIUS];

    //let arrow_top_px =   [ground_px[0] + p.speed.x * SPEED_SCALE,
    //                      ground_px[1] + p.speed.y * SPEED_SCALE];
    //let angle = Math.atan(p.speed.x, p.speed.y); // Angle of the speed vector relative to North
    //let arrow_left_px =  [arrow_top_px[0] + ARROW_HEAD_LENGTH * Math.sin(angle-ARROW_HEAD_ANGLE/2),
    //                      arrow_top_px[1] - ARROW_HEAD_LENGTH * Math.cos(angle-ARROW_HEAD_ANGLE/2)];
    //let arrow_right_px = [arrow_top_px[0] + ARROW_HEAD_LENGTH * Math.sin(angle+ARROW_HEAD_ANGLE/2),
    //                      arrow_top_px[1] - ARROW_HEAD_LENGTH * Math.cos(angle+ARROW_HEAD_ANGLE/2)];
    // let speed_lines = [[ground_c, arrow_top_px], [arrow_left_px, arrow_top_px, arrow_right_px]]
    //    .map(clist => clist.map(c => map.getCoordinateFromPixel(c)));

    let circle_ftr = new Feature({geometry: new Point(px2c(circle_center_px))});
    circle_ftr.setStyle(balloon_circle_style);

    let height_line_ftr = new Feature({geometry: new LineString([ground_c, px2c(circle_bottom_px)])});
    let hours = date.substr(11, 2);
    let minutes = date.substr(14, 2);
    let seconds = date.substr(17, 2);
    let label = hours === '00' ? `${Number(minutes)}´${seconds}´´` : `${Number(hours)}:${minutes}´`;
    height_line_ftr.set('label', label);
    height_line_ftr.setStyle(balloon_height_style);
    return [circle_ftr, height_line_ftr];
}

function update_trajectory_table(geoJSON) {
    const coords = (p) =>
        Math.abs(p.y) + "°" + (p.y>=0?"N":"S") + ";" + Math.abs(p.x) + "°" + (p.x>=0?"W":"E") + "@" +
        p.z[0] + "…" + p.z[1] + "m";
    d3.select("#trajectory_table")
        .style('display', null) // show again
        .selectAll("tr.item").data(geoJSON.features.map(p => p.properties)).enter()
        .append("tr")
        .attr("class", "item")
        .html(p => `
            <td>${coords(p.cell)}</td>
            <td>${p.time.split('T')[1]}</td>
            <td>${p.pressure}hPa</td>
            <td>${p.volume ? p.volume+'m³' : '&mdash;'}</td>
            <td>${p.rho >= 1 ? p.rho+"kg" : Math.round(1000*p.rho)+"g"}/m³</td>
            <td>${Math.abs(p.position.x)}°${p.position.x>0 ? 'E' : 'W'}</td>
            <td>${Math.abs(p.position.y)}°${p.position.y>0 ? 'N' : 'S'}</td>
            <td>${p.position.z}m</td>
            <td>${p.speed.x}m/s</td>
            <td>${p.speed.y}m/s</td>
            <td>${p.speed.z}m/s</td>
            <td>${p.move.x}m</td>
            <td>${p.move.y}m</td>
            <td>${p.move.z}m</td>
            <td>${p.move.t}s</td>
        `);
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
    display_trajectory(geojson);
    update_trajectory_table(geojson);
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
        //console.log("---------------");
        let properties = ftr.getProperties();
        Object.getOwnPropertyNames(properties).forEach((name) => {
            let value = properties[name];
            if (value instanceof Object) {
                Object.getOwnPropertyNames(value).forEach((sub_name) => {
                    let sub_value = value[sub_name];
                    //console.log(`${name}_${sub_name} = ${sub_value}`);
                    d3.select(`.position_details .${name}_${sub_name}`).text(sub_value);
                });
            } else {
                //console.log(`${name} = ${value}`);
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
d3.select('#trajectory_table')
    .style('display', 'none');
d3.select('[name=model]')
    .on('click change keypress', update_available_dates);
map.on('pointermove', (evt) => {
    let feature = null;
    map.forEachFeatureAtPixel(evt.pixel, ftr => { if(ftr.getGeometry() instanceof Point) { feature = ftr; }});
    display_feature_details(feature); // feature may be null
});
display_feature_details(null);
