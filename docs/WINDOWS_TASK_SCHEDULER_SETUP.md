# Windows Task Scheduler Setup for Log Cleanup

This guide explains how to set up automated log cleanup on Windows using Task Scheduler to run the `scripts/cleanup_logs.py` script daily.

## Prerequisites

- Windows 10/11 or Windows Server
- Python 3.7+ installed and accessible from PATH
- Gmail Automation project cloned to your local machine

## Step-by-Step Setup

### 1. Open Task Scheduler

1. Press `Win + R` to open the Run dialog
2. Type `taskschd.msc` and press Enter
3. Alternatively, search for "Task Scheduler" in the Start menu

### 2. Create a New Task

1. In Task Scheduler, click **"Create Task..."** in the Actions panel (right side)
2. This opens the Create Task dialog

### 3. General Tab Configuration

1. **Name**: `Gmail Automation Log Cleanup`
2. **Description**: `Daily cleanup of old log files and archived JSON files older than 30 days`
3. **Security Options**:
   - Select **"Run whether user is logged on or not"** if you want it to run without being logged in
   - Select **"Run with highest privileges"** if needed for file access
   - Choose the appropriate user account (usually your current user)

### 4. Triggers Tab Configuration

1. Click **"New..."** to create a new trigger
2. **Begin the task**: `On a schedule`
3. **Settings**: `Daily`
4. **Start**: Choose a time when the system is likely to be on (e.g., 2:00 AM)
5. **Recur every**: `1 days`
6. **Advanced settings**:
   - Check **"Enabled"**
   - Optionally check **"Stop task if it runs longer than"** and set to `30 minutes`
7. Click **"OK"**

### 5. Actions Tab Configuration

1. Click **"New..."** to create a new action
2. **Action**: `Start a program`
3. **Program/script**: 
   ```
   python
   ```
   Or use the full path if Python is not in PATH:
   ```
   C:\Users\YourUsername\AppData\Local\Programs\Python\Python311\python.exe
   ```

4. **Add arguments (optional)**:
   ```
   scripts\cleanup_logs.py
   ```

5. **Start in (optional)**:
   ```
   C:\path\to\your\gmail-automation-project
   ```
   Replace with the actual path to your project directory

6. Click **"OK"**

### 6. Conditions Tab Configuration

1. **Power**:
   - Uncheck **"Start the task only if the computer is on AC power"** if you want it to run on battery
   - Uncheck **"Stop if the computer switches to battery power"** if applicable

2. **Network**:
   - You can leave network conditions as default since the cleanup script works offline

### 7. Settings Tab Configuration

1. **Allow task to be run on demand**: ✅ Checked
2. **Run task as soon as possible after a scheduled start is missed**: ✅ Checked  
3. **If the task fails, restart every**: `15 minutes`
4. **Attempt to restart up to**: `3 times`
5. **Stop the task if it runs longer than**: ✅ Checked, `30 minutes`
6. **If the running task does not end when requested, force it to stop**: ✅ Checked

### 8. Finish Setup

1. Click **"OK"** to create the task
2. If prompted, enter your Windows password to save the task
3. The task should now appear in the Task Scheduler Library

## Testing the Task

### Manual Test Run

1. Find your task in the Task Scheduler Library
2. Right-click on **"Gmail Automation Log Cleanup"**
3. Select **"Run"**
4. Check the **"Last Run Result"** column to verify it completed successfully (should show `0x0`)

### Check Logs

1. Navigate to your project directory
2. Look for `cleanup_logs.log` file
3. Review the log contents to ensure the script ran correctly

### Verify Cleanup

1. Check if old log files in the `logs/` directory were removed
2. Check if old archived JSON files were removed
3. Review the summary in `cleanup_logs.log`

## Troubleshooting

### Common Issues

**Task runs but doesn't seem to work:**
- Check the **"Start in"** directory is set correctly
- Verify Python is in PATH or use full Python path
- Check file permissions for the project directory

**Task fails to start:**
- Verify the user account has proper permissions
- Check if Python path is correct
- Ensure the project directory path is accessible

**Task shows error 0x1:**
- Python script had an error
- Check `cleanup_logs.log` for error details
- Verify all file paths are correct

### Viewing Task History

1. In Task Scheduler, select your task
2. Click the **"History"** tab at the bottom
3. Review recent task executions and any error messages

### Manual Script Testing

Before setting up the scheduled task, test the script manually:

```cmd
cd C:\path\to\your\gmail-automation-project
python scripts\cleanup_logs.py
```

## Advanced Configuration

### Running with Different Parameters

If you want to customize the cleanup (e.g., different retention period), you can modify the script or create wrapper scripts with different parameters.

### Email Notifications

You can add email notifications by:
1. Going to the **Actions** tab
2. Adding a second action to **"Send an e-mail"**
3. Configuring SMTP settings (requires local SMTP server)

### Multiple Schedules

You can create multiple triggers for different schedules:
- Daily for regular cleanup
- Weekly for more thorough cleanup
- Monthly for archive maintenance

## Security Considerations

- Run the task with the minimum required privileges
- Ensure the cleanup script has appropriate file access permissions
- Consider using a dedicated service account for automated tasks
- Review logs regularly to ensure the task is working correctly

## Log File Locations

After setup, you can monitor the following logs:
- `cleanup_logs.log` - Cleanup script output
- Task Scheduler History - Task execution status
- Windows Event Logs - System-level task information

The automated cleanup will help maintain your Gmail Automation project by:
- Preventing log files from growing too large
- Removing archived error logs older than 30 days  
- Cleaning up temporary files
- Providing detailed cleanup reports
