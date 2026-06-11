import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.text.SimpleDateFormat;
import java.util.Date;

public class GitSavePlugin extends JavaPlugin implements CommandExecutor {

    @Override
    public void onEnable() {
        getCommand("save-all").setExecutor(this);
        getLogger().info("GitSavePlugin enabled!");
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!command.getName().equalsIgnoreCase("save-all")) return false;

        // Save the world first
        getServer().dispatchCommand(getServer().getConsoleSender(), "save-all");

        sender.sendMessage("§a[GitSave] §fRunning git backup...");

        getServer().getScheduler().runTaskAsynchronously(this, () -> {
            try {
                File serverDir = new File(".");
                String date = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date());

                String[] gitAdd    = {"cmd.exe", "/c", "git add ."};
                String[] gitCommit = {"cmd.exe", "/c", "git commit -m \"" + date + "\""};
                String[] gitPush   = {"cmd.exe", "/c", "git push"};

                run(gitAdd, serverDir);
                run(gitCommit, serverDir);
                run(gitPush, serverDir);

                getServer().getScheduler().runTask(this, () ->
                    sender.sendMessage("§a[GitSave] §fDone! Pushed to GitHub: §e" + date)
                );
            } catch (Exception e) {
                getLogger().severe("Git backup failed: " + e.getMessage());
                getServer().getScheduler().runTask(this, () ->
                    sender.sendMessage("§c[GitSave] Git backup failed! Check console.")
                );
            }
        });

        return true;
    }

    private void run(String[] cmd, File dir) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(dir);
        pb.redirectErrorStream(true);
        Process p = pb.start();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
            String line;
            while ((line = r.readLine()) != null) getLogger().info("[Git] " + line);
        }
        p.waitFor();
    }
}
