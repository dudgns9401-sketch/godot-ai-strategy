shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D heightmap : hint_default_black, filter_linear_mipmap;
uniform sampler2D normalmap : hint_normal, filter_linear_mipmap;

uniform float height_scale : hint_range(0.0, 100.0) = 15.0;
uniform vec4 terrain_color : source_color = vec4(0.35, 0.45, 0.3, 1.0);
uniform float roughness : hint_range(0.0, 1.0) = 0.85;
uniform float uv_scale = 1.0;

void vertex() {
	vec2 scaled_uv = UV * uv_scale;
	float h = texture(heightmap, scaled_uv).r;
	VERTEX.y += h * height_scale;
}

void fragment() {
	vec2 scaled_uv = UV * uv_scale;
	ALBEDO = terrain_color.rgb;
	ROUGHNESS = roughness;

	// Apply 3D Normal Map
	vec3 n = texture(normalmap, scaled_uv).rgb;
	NORMAL_MAP = n;
	NORMAL_MAP_DEPTH = 1.0;
}
