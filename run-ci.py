import os
import shutil
import subprocess

os.environ['PATCHWORK_TOKEN'] = '608fb4b4a5a205fd13dd93506ae32401376e56dd'
os.environ['GITHUB_TOKEN'] = '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'
os.environ['EMAIL_TOKEN'] = 'pkaolkywyojajhwn'

from cibase import CiBase, Verdict

class BuildKernel(CiBase):
    name = "buildkernel"
    display_name = "Build Kernel"
    desc = "Builds Linux kernel for use with test-runner"
    depends = ['fetch']
    submit_pw = False
    disable_src_dir = True
    version = '5.16'
    kernel_dir = "/linux-bin"

    def config(self):
        print("config")
        if not self.settings:
            self.kernel_path = '%s/um-linux-%s' % (self.kernel_dir, self.version)
            return

        if 'kernel_dir' in self.settings:
            self.kernel_dir = self.settings['kernel_dir']

            # If path is relative, assume under GITHUB_WORKSPACE
            if not os.path.isabs(self.kernel_dir):
                if not os.environ.get('GITHUB_WORKSPACE', None):
                    raise Exception('GITHUB_WORKSPACE must be used with relative paths')

                self.kernel_dir = os.path.join(os.environ['GITHUB_WORKSPACE'],
                                                self.kernel_dir)

        if 'version' in self.settings:
            self.version = self.settings['version']

        self.kernel_path = '%s/um-linux-%s' % (self.kernel_dir, self.version)

    def run(self):
        self.config()

        # Kernel already built
        if os.path.exists(self.kernel_path):
            print("Kernel already built: %s" % self.kernel_path)
            self.success()

        if os.path.exists('/tmp/linux-git'):
            shutil.rmtree('/tmp/linux-git')

        (ret, _, _) = self.run_cmd('git', 'clone', '-b', 'v%s' % self.version, '--depth=1',
                            'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
                            '/tmp/linux-git')
        if ret:
            self.add_failure_end_test("Could not clone linux")

        self.src_dir = '/tmp/linux-git'

        (ret, _, _) = self.run_cmd('make', 'ARCH=um', 'x86_64_defconfig')
        if ret:
            self.add_failure_end_test('Could not configure linux kernel')

        iwd_kernel_config = os.path.join(self.args.src_path, 'tools/test_runner_kernel_config')

        (ret, _, _) = self.run_cmd('sh', iwd_kernel_config)
        if ret:
            self.add_failure_end_test('Could not configure IWD kernel options')

        subprocess.run('yes "" | make ARCH=um -j4', shell=True, cwd='/tmp/linux-git')

        if not os.path.exists(os.path.dirname(self.kernel_path)):
            os.mkdir(os.path.dirname(self.kernel_path))

        shutil.copy('/tmp/linux-git/linux', self.kernel_path)
        shutil.rmtree('/tmp/linux-git')

        self.success()

class BuildHostapd(CiBase):
    name = "buildhostapd"
    display_name = "Build Hostapd/WpaSupplicant"
    desc = "Builds hostapd and wpa_supplicant for use with test-runner"
    depends = ['fetch']
    submit_pw = False
    disable_src_dir = True
    version = '2_10'
    bin_dir = "/hostapd"

    def config(self):
        if not self.settings:
            self.ldebug("No settings, returning")
            return

        if 'bin_dir' in self.settings:
            self.bin_dir = self.settings['bin_dir']

            # If path is relative, assume under GITHUB_WORKSPACE
            if not os.path.isabs(self.bin_dir):
                if not os.environ.get('GITHUB_WORKSPACE', None):
                    raise Exception('GITHUB_WORKSPACE must be used with relative paths')

                self.bin_dir = os.path.join(os.environ['GITHUB_WORKSPACE'],
                                                self.bin_dir)

        if 'version' in self.settings:
            self.version = self.settings['version']

    def run(self):
        self.config()

        os.system('ls %s' % self.bin_dir)

        wpa_s = os.path.join(self.bin_dir, 'wpa_supplicant_%s' % self.version)
        wpa_s_cli = os.path.join(self.bin_dir, 'wpa_cli_%s' % self.version)
        hostapd = os.path.join(self.bin_dir, 'hostapd_%s' % self.version)
        hostapd_cli = os.path.join(self.bin_dir, 'hostapd_cli_%s' % self.version)

        exists = [os.path.exists(p) for p in [wpa_s, wpa_s_cli, hostapd, hostapd_cli]]
        if all(exists):
            self.ldebug("hostapd/wpa_supplicant already built, skipping")
            self.success()

        if os.path.exists('/tmp/hostap'):
            shutil.rmtree('/tmp/hostap')

        (ret, _, _) = self.run_cmd('git', 'clone', '-b', 'hostap_%s' % self.version, '--depth=1',
                            'http://w1.fi/hostap.git', '/tmp/hostap')
        if ret:
            self.add_failure_end_test("Could not clone hostap")

        shutil.copy(self.args.src_path + '/doc/hostapd.config', '/tmp/hostap/hostapd/.config')

        self.src_dir = '/tmp/hostap/hostapd'
        (ret, _, _) = self.run_cmd('make', '-j4')
        if ret:
            self.add_failure_end_test("Could not build hostapd")

        if not os.path.exists(self.bin_dir):
            os.mkdir(self.bin_dir)

        shutil.copy(self.src_dir + '/hostapd', hostapd)
        shutil.copy(self.src_dir + '/hostapd_cli', hostapd_cli)

        self.src_dir = '/tmp/hostap/wpa_supplicant'
        shutil.copy(self.src_dir + '/defconfig', self.src_dir + '/.config')

        (ret, _, _) = self.run_cmd('make', '-j4')
        if ret:
            self.add_failure_end_test("Could not build wpa_supplicant")

        shutil.copy(self.src_dir + '/wpa_supplicant', wpa_s)
        shutil.copy(self.src_dir + '/wpa_cli', wpa_s_cli)

        shutil.rmtree('/tmp/hostap')

        self.success()

class TestRunner(CiBase):
    name = "testrunner"
    display_name = "Autotest Runner"
    desc = "Runs IWD's autotest framework"
    depends = ['buildmake', 'buildkernel', 'buildhostapd']
    inherit_src = 'build'
    kernel_path = '/linux'
    tests = None
    log_dir = '/tmp/logs'
    result = '/tmp/result/result.txt'

    def config(self):
        # Use buildkernel path by default, and if kernel_path is set use that.
        self.kernel_path = super().suite['buildkernel'].kernel_path
        hostapd_path = super().suite['buildhostapd'].bin_dir
        hostapd_version = super().suite['buildhostapd'].version

        for bin in ['hostapd', 'hostapd_cli', 'wpa_supplicant', 'wpa_cli']:
            vbin = '%s/%s_%s' % (hostapd_path, bin, hostapd_version)
            (ret, stdout, stderr) = self.run_cmd('ln', '-s', vbin, '%s/%s' % (self.src_dir, bin))
            if ret:
                self.ldebug("Failed to symlink hostapd binaries")
                self.ldebug(stderr)

        if not self.settings:
            return

        if 'kernel_path' in self.settings:
            self.kernel_path = self.settings['kernel_path']

        if 'tests' in self.settings:
            self.tests = self.settings['tests'].split(',')

        if 'log_dir' in self.settings:
            self.log_dir = self.settings['log_dir']

            if not os.path.isabs(self.log_dir):
                if not os.environ.get('GITHUB_WORKSPACE', None):
                    raise Exception('GITHUB_WORKSPACE must be used with relative paths')

                self.log_dir = os.path.join(os.environ['GITHUB_WORKSPACE'],
                                                self.log_dir)

    def run(self):
        self.ldebug("##### Run autotest framework #####")

        self.config()

        os.environ['PATH'] = self.src_dir + ':' + os.environ['PATH']

        if not os.path.exists(os.path.dirname(self.result)):
            os.makedirs(os.path.dirname(self.result))

        args = ['./tools/test-runner', '-k', self.kernel_path,
                '--result', self.result, '--log', self.log_dir]

        if self.tests:
            args.extend(['-A', ','.join(self.tests)])

        (ret, stdout, stderr) = self.run_cmd(*args)

        with open(self.result, 'r') as f:
            r = f.read()

        if r != 'PASS':
            self.submit_result(Verdict.FAIL, "test-runner - FAIL: " + stderr)
            self.add_failure_end_test(stderr)

        self.submit_result(Verdict.PASS, "test-runner PASS")
        self.success()

CiBase.run()
CiBase.print_results()
