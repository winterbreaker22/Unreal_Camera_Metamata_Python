import unreal
import os

umap = '/Game/ThirdPerson/Maps/ThirdPersonMap'
level_sequence = '/Game/first_seq'
outdir = os.path.abspath(os.path.join(unreal.Paths().project_dir(), 'Saved/MovieRenders'))

# Get movie queue subsystem for editor
subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
queue = subsystem.get_queue()
executor = unreal.MoviePipelinePIEExecutor()

# Optional: empty queue first
for job in queue.get_jobs():
    queue.delete_job(job)

# Create new movie pipeline job
job = queue.allocate_new_job()
job.set_editor_property('map', unreal.SoftObjectPath(umap))
job.set_editor_property('sequence', unreal.SoftObjectPath(level_sequence))

config = job.get_configuration()

# Set up rendering settings
render_pass_settings = config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
output_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
output_setting.output_directory = unreal.DirectoryPath(outdir)

# Switch to JPEG output
jpeg_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_JPG)

def generate_xmp_metadata():

    # Retrieve output settings from the job's configuration
    output_setting = job.get_configuration().find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    output_dir = output_setting.output_directory.path  
    file_name_format = output_setting.file_name_format  

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Load level sequence asset to get playback range and frame rate
    seq_asset = unreal.EditorAssetLibrary.load_asset(level_sequence)

    cine_camera_actor = None

    level_actors = unreal.EditorLevelLibrary.get_selected_level_actors()
    if not level_actors:
        level_actors = unreal.EditorLevelLibrary.get_all_level_actors()  # Can replace this with proper alternative if available
    
    for actor in level_actors:
        if isinstance(actor, unreal.CineCameraActor):
            cine_camera_actor = actor
            break  

    if not cine_camera_actor:
        unreal.log_error("No Cine Camera Actor found in the Level.")
        return

    playback_range = seq_asset.get_playback_range()
    start_frame = playback_range.get_start_frame() 
    end_frame = playback_range.get_end_frame()     
    frame_rate = seq_asset.get_display_rate()

    # Calculate the frame duration in seconds
    frame_duration = 1.0 / frame_rate.numerator * frame_rate.denominator

    unreal.log(f"Generating XMP metadata for frames {start_frame} to {end_frame}.")

    # Loop through each frame in the sequence
    for frame in range(start_frame, end_frame):
        # Set the sequence to the specific frame using FFrameNumber
        current_time = frame * frame_duration  # Convert frame to seconds
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(current_time)

        # Get camera transform and FOV at the current frame
        transform = cine_camera_actor.get_actor_transform()
        fov = cine_camera_actor.get_cine_camera_component().field_of_view

        # Extract position and rotation in world space
        location = transform.translation
        rotation = transform.rotation.euler()  # Rotation in XYZ (pitch, yaw, roll)

        # Generate filename based on the Movie Render Queue format
        frame_number_str = "." + str(frame).zfill(4)  # Pad frame numbers as needed (e.g., 0001)
        jpeg_filename = frame_number_str + ".jpg"
        xmp_filename = os.path.splitext(jpeg_filename)[0] + ".xmp"
        xmp_filepath = os.path.join(output_dir, xmp_filename)

        # Define the XMP metadata content
        xmp_content = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
        <x:xmpmeta xmlns:x='adobe:ns:meta/'>
          <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
            <rdf:Description rdf:about=''
                xmlns:exif='http://ns.adobe.com/exif/1.0/'>
              <exif:GPSLatitude>{location.y}</exif:GPSLatitude>
              <exif:GPSLongitude>{location.x}</exif:GPSLongitude>
              <exif:GPSAltitude>{location.z}</exif:GPSAltitude>
              <exif:Orientation>1</exif:Orientation>
              <exif:CameraOrientationX>{rotation.x}</exif:CameraOrientationX>
              <exif:CameraOrientationY>{rotation.y}</exif:CameraOrientationY>
              <exif:CameraOrientationZ>{rotation.z}</exif:CameraOrientationZ>
              <exif:FocalLength>{fov}</exif:FocalLength>
            </rdf:Description>
          </rdf:RDF>
        </x:xmpmeta>
        <?xpacket end='w'?>"""

        # Write the XMP metadata to a file
        with open(xmp_filepath, "w") as xmp_file:
            xmp_file.write(xmp_content)

    unreal.log("XMP metadata generation completed.")

# Error and completion callbacks
error_callback = unreal.OnMoviePipelineExecutorErrored()
def movie_error(pipeline_executor, pipeline_with_error, is_fatal, error_text):
    print("Error in pipeline:", pipeline_executor)
    print("Pipeline with error:", pipeline_with_error)
    print("Is fatal:", is_fatal)
    print("Error text:", error_text)
error_callback.add_callable(movie_error)

def movie_finished(pipeline_executor, success):
    print("Pipeline finished:", pipeline_executor)
    print("Success:", success)

finished_callback = unreal.OnMoviePipelineExecutorFinished()
finished_callback.add_callable(movie_finished)

# Assign the callbacks and start the rendering process
executor = subsystem.render_queue_with_executor(unreal.MoviePipelinePIEExecutor)
if executor:
    executor.set_editor_property('on_executor_errored_delegate', error_callback)
    executor.set_editor_property('on_executor_finished_delegate', finished_callback)

generate_xmp_metadata()