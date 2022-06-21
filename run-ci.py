import os
import shutil
import subprocess

from cibase import CiBase, Verdict, path_resolve

class BuildKernel(CiBase):
    name = "buildkernel"
    display_name = "Build Kernel"
    desc = "Builds Linux kernel for use with test-runner"
    depends = ['fetch']
    submit_pw = False
    disable_src_dir = True
    version = os.environ.get('INPUT_KERNEL', '5.16')
    kernel_dir = "/linux-bin"

    def config(self):
        if not self.settings:
            self.kernel_path = '%s/um-linux-%s' % (self.kernel_dir, self.version)
            return

        if 'kernel_dir' in self.settings:
            self.kernel_dir = path_resolve(self.settings['kernel_dir'])

        self.kernel_path = '%s/um-linux-%s' % (self.kernel_dir, self.version)

    def run(self):
        self.config()

        workdir = os.path.join(self.workdir, 'linux-git/')

        # Kernel already built
        if os.path.exists(self.kernel_path):
            print("Kernel already built: %s" % self.kernel_path)
            self.success()

        if os.path.exists(workdir):
            shutil.rmtree(workdir)

        (ret, _, _) = self.run_cmd('git', 'clone', '-b', 'v%s' % self.version, '--depth=1',
                            'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
                            workdir)
        if ret:
            self.add_failure_end_test("Could not clone linux")

        self.src_dir = workdir

        (ret, _, _) = self.run_cmd('make', 'ARCH=um', 'x86_64_defconfig')
        if ret:
            self.add_failure_end_test('Could not configure linux kernel')

        iwd_kernel_config = os.path.join(self.args.src_path, 'tools/test_runner_kernel_config')

        (ret, _, _) = self.run_cmd('sh', iwd_kernel_config)
        if ret:
            self.add_failure_end_test('Could not configure IWD kernel options')

        subprocess.run('yes "" | make ARCH=um -j4', shell=True, cwd=self.src_dir)

        if not os.path.exists(os.path.dirname(self.kernel_path)):
            os.mkdir(os.path.dirname(self.kernel_path))

        shutil.copy(os.path.join(workdir, 'linux'), self.kernel_path)
        shutil.rmtree(workdir)

        self.success()

class BuildHostapd(CiBase):
    name = "buildhostapd"
    display_name = "Build Hostapd/WpaSupplicant"
    desc = "Builds hostapd and wpa_supplicant for use with test-runner"
    depends = ['fetch']
    submit_pw = False
    disable_src_dir = True
    version = os.environ.get('INPUT_HOSTAPD_VERSION', '2_10')
    bin_dir = "/hostapd"

    def config(self):
        if not self.settings:
            self.ldebug("No settings, returning")
            return

        if 'bin_dir' in self.settings:
            self.bin_dir = path_resolve(self.settings['bin_dir'])

    def build_hostapd(self, hapd_path, hapd_cli_path):
        self.src_dir = os.path.join(self.workdir, 'hostapd/')
        shutil.copy(self.args.src_path + '/doc/hostapd.config', self.src_dir + '/.config')

        (ret, _, _) = self.run_cmd('make', '-j4')
        if ret:
            self.add_failure_end_test("Could not build hostapd")

        shutil.copy(self.src_dir + '/hostapd', hapd_path)
        shutil.copy(self.src_dir + '/hostapd_cli', hapd_cli_path)

    def build_wpa_supplicant(self, wpa_path, wpa_cli_path):
        self.src_dir = os.path.join(self.workdir, 'wpa_supplicant/')
        shutil.copy(self.src_dir + '/defconfig', self.src_dir + '/.config')

        (ret, _, _) = self.run_cmd('make', '-j4')
        if ret:
            self.add_failure_end_test("Could not build wpa_supplicant")

        shutil.copy(self.src_dir + '/wpa_supplicant', wpa_path)
        shutil.copy(self.src_dir + '/wpa_cli', wpa_cli_path)

    def run(self):
        self.config()

        self.workdir = os.path.join(self.workdir, 'hostap/')

        hostapd = os.path.join(self.bin_dir, 'hostapd_%s' % self.version)
        hostapd_cli = os.path.join(self.bin_dir, 'hostapd_cli_%s' % self.version)
        wpa_s = os.path.join(self.bin_dir, 'wpa_supplicant_%s' % self.version)
        wpa_s_cli = os.path.join(self.bin_dir, 'wpa_cli_%s' % self.version)

        wpa_exists = all([os.path.exists(p) for p in [wpa_s, wpa_s_cli]])
        hapd_exists = all([os.path.exists(p) for p in [hostapd, hostapd_cli]])

        if wpa_exists and hapd_exists:
            self.success()

        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir)

        if not os.path.exists(self.bin_dir):
            os.mkdir(self.bin_dir)

        (ret, _, _) = self.run_cmd('git', 'clone', '-b', 'hostap_%s' % self.version,
                            '--depth=1', 'http://w1.fi/hostap.git', self.workdir)
        if ret:
            self.add_failure_end_test("Could not clone hostap")

        if not hapd_exists:
            self.build_hostapd(hostapd, hostapd_cli)

        if not wpa_exists:
            self.build_wpa_supplicant(wpa_s, wpa_s_cli)

        shutil.rmtree(self.workdir)

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
            self.kernel_path = path_resolve(self.settings['kernel_path'])

        if 'tests' in self.settings:
            self.tests = self.settings['tests'].split(',')

        if 'log_dir' in self.settings:
            self.log_dir = path_resolve(self.settings['log_dir'])

        if 'result' in self.settings:
            self.result = path_resolve(self.settings['result'])

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

        (ret, stdout, stderr) = self.run_cmd(*args, timeout=1800)

        with open(self.result, 'r') as f:
            r = f.read()

        if r != 'PASS':
            self.submit_result(Verdict.FAIL, "test-runner - FAIL: " + stderr)
            self.add_failure_end_test(stderr)

        self.submit_result(Verdict.PASS, "test-runner PASS")
        self.success()

class ClangBuild(CiBase):
    name = "clang"
    display_name = "Clang Build"
    desc = "Build IWD using clang compiler"
    depends = ['setupell']

    def run(self):
        env = os.environ.copy()
        env['CC'] = 'clang'

        # bootstrap-configure
        (ret, stdout, stderr) = self.run_cmd("./bootstrap-configure", env=env)
        if ret:
            self.submit_result(Verdict.FAIL,
                               "Clang IWD - Configuration FAIL: " + stderr)
            self.add_failure_end_test(stderr)

        # make
        (ret, stdout, stderr) = self.run_cmd("make", "-j4")
        if ret:
            self.submit_result(Verdict.FAIL, "Clang IWD - make FAIL: " + stderr)
            self.add_failure_end_test(stderr)

        self.submit_result(Verdict.PASS, "clang PASS")
        self.success()

CiBase.run()
CiBase.print_results()
