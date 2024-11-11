import unreal
import os
import time
import math

# Get the current map's full path
current_map = unreal.EditorLevelLibrary.get_editor_world().get_path_name()

# Check for an active level sequence
level_sequence = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
if not level_sequence:
    print("No active level sequence found.")
    exit()  # Exit if no sequence is active

level_sequence_path = unreal.SoftObjectPath(level_sequence.get_path_name())

# Define the output directory
outdir = os.path.abspath(os.path.join(unreal.Paths().project_dir(), 'Saved/MovieRenders'))

# Get movie queue subsystem for editor
subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
queue = subsystem.get_queue()

# Optional: empty queue first
for job in queue.get_jobs():
    queue.delete_job(job)

# Create new movie pipeline job
job = queue.allocate_new_job()
job.set_editor_property('map', unreal.SoftObjectPath(current_map))  # Use full map path
job.set_editor_property('sequence', level_sequence_path)  # Set the dynamically found sequence

config = job.get_configuration()

# Set up rendering settings
render_pass_settings = config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
output_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
output_setting.output_directory = unreal.DirectoryPath(outdir)

# Switch to JPEG output
jpeg_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_JPG)

# Delay to ensure PIE is initialized
latent_info = unreal.LatentActionInfo()  # Create latent action info
unreal.SystemLibrary.delay(None, 5, latent_info)  # Use latent_info for the delay

def generate_xmp_metadata():
    # Retrieve output settings from the job's configuration
    output_setting = job.get_configuration().find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    output_dir = output_setting.output_directory.path  
    file_name_format = output_setting.file_name_format  

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    cine_camera_actor = None

    level_actors = unreal.EditorLevelLibrary.get_selected_level_actors()
    if not level_actors:
        level_actors = unreal.EditorLevelLibrary.get_all_level_actors()
    
    for actor in level_actors:
        if isinstance(actor, unreal.CineCameraActor):
            cine_camera_actor = actor
            break  

    if not cine_camera_actor:
        unreal.log_error("No Cine Camera Actor found in the Level.")
        return

    playback_range = level_sequence.get_playback_range()
    start_frame = playback_range.get_start_frame() 
    end_frame = playback_range.get_end_frame()     
    frame_rate = level_sequence.get_display_rate()

    # Calculate the frame duration in seconds
    frame_duration = 1.0 / frame_rate.numerator * frame_rate.denominator

    unreal.log(f"Generating XMP metadata for frames {start_frame} to {end_frame}.")

    # Loop through each frame in the sequence
    for frame in range(start_frame, end_frame):
        current_time = frame * frame_duration
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(current_time)

        # Get camera transform and FOV at the current frame
        transform = cine_camera_actor.get_actor_transform()
        fov = cine_camera_actor.get_cine_camera_component().field_of_view

        # Extract position and rotation in world space
        location = transform.translation
        rotation = transform.rotation.euler()

        rx = math.radians(rotation.x)
        ry = math.radians(rotation.y)
        rz = math.radians(rotation.z)

        cos_rx, sin_rx = math.cos(rx), math.sin(rx)
        cos_ry, sin_ry = math.cos(ry), math.sin(ry)
        cos_rz, sin_rz = math.cos(rz), math.sin(rz)

        rotation_matrix = [
            [cos_ry * cos_rz, -cos_ry * sin_rz, sin_ry],
            [sin_rx * sin_ry * cos_rz + cos_rx * sin_rz, -sin_rx * sin_ry * sin_rz + cos_rx * cos_rz, -sin_rx * cos_ry],
            [-cos_rx * sin_ry * cos_rz + sin_rx * sin_rz, cos_rx * sin_ry * sin_rz + sin_rx * cos_rz, cos_rx * cos_ry]
        ]

        # Generate filename based on the Movie Render Queue format
        frame_number_str = "." + str(frame).zfill(4)
        jpeg_filename = level_sequence.get_name() + frame_number_str + ".jpeg"
        xmp_filename = os.path.splitext(jpeg_filename)[0] + ".xmp"
        xmp_filepath = os.path.join(output_dir, xmp_filename)

        # Define the XMP metadata content
        xmp_content = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
        <x:xmpmeta xmlns:x='adobe:ns:meta/'>
          <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
            <rdf:Description rdf:about=''
                xmlns:xcr='http://ns.adobe.com/xcr/1.0/'>
                <xcr:Position>{location.x} {location.y} {location.z}</xcr:Position>
                <xcr:Rotation>{rotation_matrix[0][0]} {rotation_matrix[0][1]} {rotation_matrix[0][2]} {rotation_matrix[1][0]} {rotation_matrix[1][1]} {rotation_matrix[1][2]} {rotation_matrix[2][0]} {rotation_matrix[2][1]} {rotation_matrix[2][2]}</xcr:Rotation>
              <exif:FocalLength>{fov}</exif:FocalLength>
            </rdf:Description>
          </rdf:RDF>
        </x:xmpmeta>
        <?xpacket end='w'?>"""

        with open(xmp_filepath, "w") as xmp_file:
            xmp_file.write(xmp_content)

    unreal.log("XMP metadata generation completed.")

# Define error and completion callbacks
def movie_error(pipeline_executor, pipeline_with_error, is_fatal, error_text):
    unreal.log_error(f"Error in pipeline: {error_text}")
    print("Error in pipeline:", pipeline_executor)
    print("Pipeline with error:", pipeline_with_error)
    print("Is fatal:", is_fatal)
    print("Error text:", error_text)

def movie_finished(pipeline_executor, success):
    if success:
        unreal.log("Movie pipeline finished successfully.")
    else:
        unreal.log_error("Movie pipeline failed.")
    print("Pipeline finished:", pipeline_executor)
    print("Success:", success)

# Attach the error and finished callbacks
error_callback = unreal.OnMoviePipelineExecutorErrored()
error_callback.add_callable(movie_error)

finished_callback = unreal.OnMoviePipelineExecutorFinished()
finished_callback.add_callable(movie_finished)

# Ensure PIE is ready before starting the render queue
unreal.SystemLibrary.delay(None, 5, latent_info)  # Allow additional delay time if needed

# Use class type for the executor
executor = subsystem.render_queue_with_executor(unreal.MoviePipelinePIEExecutor)

# Generate XMP metadata
generate_xmp_metadata()
