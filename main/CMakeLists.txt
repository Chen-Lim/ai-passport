idf_component_register(
    SRCS "travel_app.c"
         "travel_state.c"
         "travel_demo.c"
         "travel_ui.c"
         "../assets/fonts/travel_font_18.c"
    INCLUDE_DIRS "."
    REQUIRES bsp esp_timer esp_pm
)
