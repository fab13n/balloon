const DJANGO_PORT = 10001;
const NODEJS_PORT = 10000;

const path = require('path');
const django_server=`http://localhost:${DJANGO_PORT}`;

const HtmlWebpackPlugin = require('html-webpack-plugin');

function webpack_entry(name) {
    return new HtmlWebpackPlugin({
        template: `./src/${name}.html`,
        filename: `${name}.html`,
        inject: false });
}

module.exports = {
    mode: 'development',
    devtool: 'source-map',
    entry: {
        index: './src/index.js',
    },
    output: {
        path: path.resolve('dist'),
        filename: '[name]_bundle.js'},
    module: {
        rules: [
            { test: /\.js$/, loader: 'babel-loader', exclude: /node_modules/ }]},
    plugins: [
        webpack_entry('index'),
    ],
    devServer: {
        host: "0.0.0.0",
        port: NODEJS_PORT,
        proxy: {
            '/forecast': django_server,
            '/trajectory': django_server,
            '/column': django_server,
            '/ws': {'target': django_server.replace(/^http/, 'ws'), ws: true},
        }
    }
}
